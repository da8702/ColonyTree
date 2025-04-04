from flask import Flask, render_template, send_file, Response, request, jsonify, redirect, url_for
import os
import json
from threading import Thread
import sys
import webbrowser
import time
from datetime import datetime
import requests
import subprocess
from family_tree import Animal, Colony

# Create Flask app
app = Flask(__name__)

# Global variables for Qt application
qt_app = None
main_window = None
dash_process = None

# Global variable to store current colony
current_colony = None

def run_qt():
    """Run the PyQt5 application"""
    try:
        print("Starting PyQt5 application...")
        from PyQt5.QtWidgets import QApplication
        from family_tree import MainWindow as QtMainWindow
        
        global qt_app, main_window
        qt_app = QApplication(sys.argv)
        main_window = QtMainWindow()
        main_window.show()
        print("PyQt5 window should be visible now")
        qt_app.exec_()
    except Exception as e:
        print(f"Error starting PyQt5 application: {e}")
        print("Full error details:", sys.exc_info())

def run_dash():
    """Run the Dash application"""
    global dash_process
    try:
        print("Starting Dash application...")
        # Run Dash in a separate process
        dash_process = subprocess.Popen([sys.executable, 'tree_visualization.py'],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        print("Dash process started with PID:", dash_process.pid)
    except Exception as e:
        print(f"Error starting Dash application: {e}")
        print("Full error details:", sys.exc_info())

def is_dash_running():
    """Check if the Dash server is running"""
    try:
        response = requests.get('http://localhost:8050', timeout=1)
        return response.status_code == 200
    except:
        return False

def save_colony(colony, filename):
    """Save colony to JSON file"""
    if not os.path.exists('colonies'):
        os.makedirs('colonies')
    
    data = {
        'name': colony.name,
        'animals': []
    }
    
    for animal in colony.animals:
        animal_data = {
            'animal_id': animal.animal_id,
            'sex': animal.sex,
            'genotype': animal.genotype,
            'dob': animal.dob.isoformat(),
            'mother_id': animal.mother.animal_id if animal.mother else None,
            'father_id': animal.father.animal_id if animal.father else None
        }
        data['animals'].append(animal_data)
    
    with open(f'colonies/{filename}.json', 'w') as f:
        json.dump(data, f, indent=4)

def load_colony(filename):
    """Load colony from JSON file"""
    with open(f'colonies/{filename}.json', 'r') as f:
        data = json.load(f)
    
    colony = Colony(data['name'])
    
    # First pass: create all animals
    for animal_data in data['animals']:
        animal = Animal(
            animal_data['animal_id'],
            animal_data['sex'],
            animal_data['genotype'],
            datetime.strptime(animal_data['dob'], '%Y-%m-%d').date(),
            None,  # mother will be set in second pass
            None   # father will be set in second pass
        )
        colony.add_animal(animal)
    
    # Second pass: set parent relationships
    for animal_data in data['animals']:
        animal = next(a for a in colony.animals if a.animal_id == animal_data['animal_id'])
        if animal_data['mother_id']:
            mother = next(a for a in colony.animals if a.animal_id == animal_data['mother_id'])
            animal.mother = mother
        if animal_data['father_id']:
            father = next(a for a in colony.animals if a.animal_id == animal_data['father_id'])
            animal.father = father
    
    return colony

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/colonies')
def list_colonies():
    """List all available colonies"""
    if not os.path.exists('colonies'):
        os.makedirs('colonies')
    colonies = [f[:-5] for f in os.listdir('colonies') if f.endswith('.json')]
    return render_template('colonies.html', colonies=colonies)

@app.route('/colony/new', methods=['GET', 'POST'])
def new_colony():
    """Create a new colony"""
    if request.method == 'POST':
        name = request.form['name']
        global current_colony
        current_colony = Colony(name)
        return redirect(url_for('view_colony'))
    return render_template('new_colony.html')

@app.route('/colony/load/<name>')
def load_colony_route(name):
    """Load a specific colony"""
    global current_colony
    try:
        current_colony = load_colony(name)
        # Ensure the colony name matches the file name
        current_colony.name = name
        return redirect(url_for('view_colony'))
    except Exception as e:
        return f"Error loading colony: {str(e)}", 400

@app.route('/colony/save', methods=['POST'])
def save_colony_route():
    """Save the current colony"""
    if current_colony:
        filename = request.form['filename']
        save_colony(current_colony, filename)
        return redirect(url_for('list_colonies'))
    return "No colony to save", 400

@app.route('/colony')
def view_colony():
    """View the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    return render_template('view_colony.html', colony=current_colony)

@app.route('/animal/add', methods=['GET', 'POST'])
def add_animal():
    """Add a new animal to the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    if request.method == 'POST':
        try:
            animal = Animal(
                request.form['animal_id'],
                request.form['sex'],
                request.form['genotype'],
                datetime.strptime(request.form['dob'], '%Y-%m-%d').date(),
                None,  # mother will be set later
                None   # father will be set later
            )
            
            # Set parents if IDs are provided
            if request.form['mother_id']:
                mother = next((a for a in current_colony.animals if a.animal_id == request.form['mother_id']), None)
                if mother:
                    animal.mother = mother
            
            if request.form['father_id']:
                father = next((a for a in current_colony.animals if a.animal_id == request.form['father_id']), None)
                if father:
                    animal.father = father
            
            current_colony.add_animal(animal)
            return redirect(url_for('view_colony'))
        except Exception as e:
            return f"Error adding animal: {str(e)}", 400
    
    return render_template('add_animal.html', colony=current_colony)

@app.route('/visualization')
def visualization():
    """Serve the visualization page"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    return render_template('visualization.html', colony=current_colony)

@app.route('/api/colony')
def get_colony_data():
    """Get current colony data for visualization"""
    if not current_colony:
        return jsonify({'error': 'No colony loaded'}), 404
    
    data = {
        'name': current_colony.name,
        'animals': []
    }
    
    for animal in current_colony.animals:
        animal_data = {
            'animal_id': animal.animal_id,
            'sex': animal.sex,
            'genotype': animal.genotype,
            'dob': animal.dob.isoformat(),
            'mother_id': animal.mother.animal_id if animal.mother else None,
            'father_id': animal.father.animal_id if animal.father else None
        }
        data['animals'].append(animal_data)
    
    return jsonify(data)

@app.route('/colony/rename', methods=['POST'])
def rename_colony():
    """Rename the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    new_name = request.form.get('new_name')
    if not new_name:
        return "Error: New name is required", 400
    
    current_colony.name = new_name
    return redirect(url_for('view_colony'))

@app.route('/colony/rename/<old_name>', methods=['POST'])
def rename_colony_file(old_name):
    """Rename a colony file"""
    new_name = request.form.get('new_name')
    if not new_name:
        return "Error: New name is required", 400
    
    # Ensure the colonies directory exists
    if not os.path.exists('colonies'):
        os.makedirs('colonies')
    
    old_path = os.path.join('colonies', f'{old_name}.json')
    new_path = os.path.join('colonies', f'{new_name}.json')
    
    # Check if the old file exists
    if not os.path.exists(old_path):
        return "Error: Colony file not found", 404
    
    # Check if the new name already exists
    if os.path.exists(new_path):
        return "Error: A colony with this name already exists", 400
    
    try:
        # If this is the currently loaded colony, update its name in memory
        global current_colony
        if current_colony and current_colony.name == old_name:
            current_colony.name = new_name
        
        # Rename the file
        os.rename(old_path, new_path)
        
        return redirect(url_for('list_colonies'))
    except Exception as e:
        return f"Error renaming colony: {str(e)}", 500

if __name__ == '__main__':
    print("Starting Animal Colony Manager...")
    
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        print("Creating templates directory...")
        os.makedirs('templates')
    
    # Start Qt application in a separate thread
    print("Starting PyQt5 thread...")
    qt_thread = Thread(target=run_qt)
    qt_thread.daemon = True
    qt_thread.start()
    
    # Start Dash server in a separate process
    print("Starting Dash process...")
    run_dash()
    
    # Wait a moment for servers to start
    time.sleep(5)
    
    # Open the web browser
    print("Opening web browser...")
    webbrowser.open('http://localhost:5000')
    
    # Run Flask server
    print("Starting Flask server...")
    app.run(debug=False, port=5000) 
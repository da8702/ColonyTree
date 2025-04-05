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
from models import Animal, Colony

# Create Flask app
app = Flask(__name__)

# Global variable to store current colony
current_colony = None

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
        # Parse the date string, handling both date-only and datetime formats
        dob_str = animal_data['dob']
        if 'T' in dob_str:  # If it's a datetime string
            dob_str = dob_str.split('T')[0]  # Take just the date part
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        
        animal = Animal(
            animal_data['animal_id'],
            animal_data['sex'],
            animal_data['genotype'],
            dob,
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
    """Redirect to colonies page"""
    return redirect(url_for('list_colonies'))

@app.route('/colonies')
def list_colonies():
    """List all available colonies"""
    # Ensure the colonies directory exists
    if not os.path.exists('colonies'):
        os.makedirs('colonies')
    
    # Get list of colony files
    colonies = []
    for file in os.listdir('colonies'):
        if file.endswith('.json'):
            colonies.append(file[:-5])  # Remove .json extension
    
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

@app.route('/add_animal', methods=['GET', 'POST'])
def add_animal():
    """Add a new animal to the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            animal_id = data.get('animal_id')
            sex = data.get('sex')
            genotype = data.get('genotype')
            dob = datetime.strptime(data.get('dob'), '%Y-%m-%d')
            mother_id = data.get('mother_id')
            father_id = data.get('father_id')
            
            # Create the animal
            animal = Animal(animal_id, sex, genotype, dob)
            
            # Set parent relationships if provided
            if mother_id:
                mother = current_colony.get_animal(mother_id)
                if mother:
                    animal.mother = mother
                    mother.children.append(animal)
            
            if father_id:
                father = current_colony.get_animal(father_id)
                if father:
                    animal.father = father
                    father.children.append(animal)
            
            current_colony.add_animal(animal)
            
            # Save the colony after adding the animal
            try:
                save_colony(current_colony, current_colony.name)
                print(f"Saved colony after adding animal {animal_id}")
            except Exception as save_error:
                print(f"Error saving colony: {str(save_error)}")
            
            return jsonify({'success': True})
        except Exception as e:
            print(f"Error adding animal: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})
    
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

@app.route('/delete_animal/<animal_id>', methods=['POST'])
def delete_animal(animal_id):
    """Delete an animal from the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    try:
        # Find and remove the animal
        animal = current_colony.get_animal(animal_id)
        if animal:
            # Remove parent-child relationships
            if animal.mother:
                animal.mother.children.remove(animal)
            if animal.father:
                animal.father.children.remove(animal)
            
            # Remove the animal from the colony
            current_colony.animals.remove(animal)
            
            # Save the colony after deletion
            save_colony(current_colony, current_colony.name)
            print(f"Deleted animal {animal_id} from colony {current_colony.name}")
        else:
            print(f"Animal {animal_id} not found in colony {current_colony.name}")
    except Exception as e:
        print(f"Error deleting animal: {str(e)}")
    
    return redirect(url_for('view_colony'))

@app.route('/edit_animal/<animal_id>', methods=['POST'])
def edit_animal(animal_id):
    """Edit an animal in the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    try:
        # Find the animal
        animal = current_colony.get_animal(animal_id)
        if not animal:
            print(f"Animal {animal_id} not found in colony {current_colony.name}")
            return redirect(url_for('view_colony'))
        
        # Update animal properties
        animal.sex = request.form['sex']
        animal.genotype = request.form['genotype']
        animal.dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        
        # Update parent relationships
        # First remove existing relationships
        if animal.mother:
            animal.mother.children.remove(animal)
        if animal.father:
            animal.father.children.remove(animal)
        
        # Set new relationships
        mother_id = request.form.get('mother_id')
        father_id = request.form.get('father_id')
        
        if mother_id:
            mother = current_colony.get_animal(mother_id)
            if mother:
                animal.mother = mother
                mother.children.append(animal)
        
        if father_id:
            father = current_colony.get_animal(father_id)
            if father:
                animal.father = father
                father.children.append(animal)
        
        # Save the colony after editing
        save_colony(current_colony, current_colony.name)
        print(f"Updated animal {animal_id} in colony {current_colony.name}")
    except Exception as e:
        print(f"Error editing animal: {str(e)}")
    
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

@app.route('/edit_animal_id', methods=['POST'])
def edit_animal_id():
    """Edit an animal's ID"""
    if not current_colony:
        return jsonify({'success': False, 'error': 'No colony loaded'})
    
    try:
        old_id = request.form.get('old_id')
        new_id = request.form.get('new_id')
        
        if not old_id or not new_id:
            return jsonify({'success': False, 'error': 'Missing ID values'})
        
        # Find the animal
        animal = current_colony.get_animal(old_id)
        if not animal:
            return jsonify({'success': False, 'error': 'Animal not found'})
        
        # Check if new ID already exists
        if current_colony.get_animal(new_id):
            return jsonify({'success': False, 'error': 'New ID already exists'})
        
        # Update the ID
        animal.animal_id = new_id
        
        # Update references in parent-child relationships
        if animal.mother:
            animal.mother.children = [new_id if child == old_id else child for child in animal.mother.children]
        if animal.father:
            animal.father.children = [new_id if child == old_id else child for child in animal.father.children]
        
        # Save the colony
        save_colony(current_colony, current_colony.name)
        print(f"Updated animal ID from {old_id} to {new_id}")
        
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error updating animal ID: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print("Starting Animal Colony Manager...")
    
    try:
        # Create templates directory if it doesn't exist
        if not os.path.exists('templates'):
            print("Creating templates directory...")
            os.makedirs('templates')
        
        # Start Dash server in a separate process
        print("Starting Dash process...")
        run_dash()
        
        # Wait a moment for servers to start
        print("Waiting for servers to start...")
        time.sleep(5)
        
        # Check if Dash server is running
        if not is_dash_running():
            print("Warning: Dash server may not have started properly")
        
        # Try to open the web browser
        try:
            print("Attempting to open web browser...")
            webbrowser.open('http://localhost:5000')
            print("Web browser opened successfully")
        except Exception as e:
            print(f"Warning: Could not open web browser automatically: {e}")
            print("Please open http://localhost:5000 in your web browser manually")
        
        # Run Flask server
        print("Starting Flask server...")
        app.run(debug=False, port=5000)
    except Exception as e:
        print(f"Error starting the application: {e}")
        print("Full error details:", sys.exc_info())
        input("Press Enter to exit...")  # Keep the window open to see the error 
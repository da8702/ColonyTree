from flask import Flask, render_template, send_file, Response, request, jsonify, redirect, url_for, session, flash
import os
import json
from threading import Thread
import sys
import webbrowser
import time
from datetime import datetime, date
import requests
import subprocess
from models import Animal, Colony
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Global variable to store current colony
current_colony = None
colonies_dir = 'colonies'

# Ensure colonies directory exists
if not os.path.exists(colonies_dir):
    os.makedirs(colonies_dir)

def run_dash():
    """Run the Dash server in a separate process"""
    subprocess.Popen(['python', 'tree_visualization.py'])

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
            'father_id': animal.father.animal_id if animal.father else None,
            'notes': animal.notes if hasattr(animal, 'notes') else None,
            'cage_id': animal.cage_id if hasattr(animal, 'cage_id') else None,
            'date_weaned': animal.date_weaned.isoformat() if hasattr(animal, 'date_weaned') and animal.date_weaned else None
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
        
        # Parse date weaned if it exists
        date_weaned = None
        if animal_data.get('date_weaned'):
            date_weaned_str = animal_data['date_weaned']
            if 'T' in date_weaned_str:  # If it's a datetime string
                date_weaned_str = date_weaned_str.split('T')[0]  # Take just the date part
            date_weaned = datetime.strptime(date_weaned_str, '%Y-%m-%d').date()
        
        # Get optional fields with fallbacks
        cage_id = animal_data.get('cage_id')
        notes = animal_data.get('notes')
        
        animal = Animal(
            animal_data['animal_id'],
            animal_data['sex'],
            animal_data['genotype'],
            dob,
            None,  # mother will be set in second pass
            None,  # father will be set in second pass
            notes,
            cage_id,
            date_weaned
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
            cage_id = data.get('cage_id')
            notes = data.get('notes')
            
            # Parse date_weaned if provided
            date_weaned = None
            if data.get('date_weaned'):
                date_weaned = datetime.strptime(data.get('date_weaned'), '%Y-%m-%d')
            
            # Create the animal
            animal = Animal(animal_id, sex, genotype, dob, None, None, notes, cage_id, date_weaned)
            
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
            'father_id': animal.father.animal_id if animal.father else None,
            'notes': getattr(animal, 'notes', None),
            'cage_id': getattr(animal, 'cage_id', None),
            'date_weaned': animal.date_weaned.isoformat() if hasattr(animal, 'date_weaned') and animal.date_weaned else None
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
    global current_colony
    if not current_colony:
        return jsonify({'success': False, 'error': 'No colony selected'}), 400
    
    try:
        # Check if the request is JSON or form data
        if request.is_json:
            data = request.get_json()
        else:
            # Process form data
            data = {
                'original_id': request.form.get('original_id', animal_id),
                'animal_id': request.form.get('animal_id'),
                'sex': request.form.get('sex'),
                'genotype': request.form.get('genotype'),
                'dob': request.form.get('dob'),
                'date_weaned': request.form.get('date_weaned'),
                'cage_id': request.form.get('cage_id'),
                'mother_id': request.form.get('mother_id'),
                'father_id': request.form.get('father_id'),
                'notes': request.form.get('notes')
            }
        
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        print(f"Received data: {data}")  # Debug print
            
        original_id = data.get('original_id', animal_id)  # Use the path parameter as fallback
        
        # Get the animal using the original ID
        animal = current_colony.get_animal_by_id(original_id)
        if not animal:
            return jsonify({'success': False, 'error': f'Animal with ID {original_id} not found'}), 404
            
        new_id = data.get('animal_id')
        sex = data.get('sex')
        genotype = data.get('genotype')
        dob = data.get('dob')
        cage_id = data.get('cage_id')
        mother_id = data.get('mother_id')
        father_id = data.get('father_id')
        notes = data.get('notes')
        date_weaned = data.get('date_weaned')
        
        print(f"Updating animal {original_id} -> {new_id}, sex={sex}, genotype={genotype}")
        
        # Update animal properties
        if animal.animal_id != new_id:
            print(f"Changing animal ID from {animal.animal_id} to {new_id}")
            # ID is changing, update all references
            current_colony.update_animal_id(animal.animal_id, new_id)
        
        animal.sex = sex
        animal.genotype = genotype
        animal.dob = dob if isinstance(dob, date) else date.fromisoformat(dob)
        animal.cage_id = cage_id
        animal.notes = notes
        
        # Update date_weaned if provided
        if date_weaned:
            animal.date_weaned = date_weaned if isinstance(date_weaned, date) else date.fromisoformat(date_weaned)
        else:
            animal.date_weaned = None
        
        # Handle mother relationship
        current_mother_id = animal.mother.animal_id if hasattr(animal.mother, 'animal_id') else animal.mother
        if mother_id != str(current_mother_id):
            print(f"Changing mother from {current_mother_id} to {mother_id}")
            # Remove from old mother's children if exists
            if animal.mother:
                old_mother = current_colony.get_animal_by_id(current_mother_id)
                if old_mother:
                    if hasattr(old_mother.children, 'remove'):
                        if animal.animal_id in old_mother.children:
                            old_mother.children.remove(animal.animal_id)
            
            # Set new mother
            if mother_id and mother_id != "None":
                new_mother = current_colony.get_animal_by_id(mother_id)
                if new_mother:
                    animal.mother = new_mother
                    if animal.animal_id not in new_mother.children:
                        new_mother.children.append(animal.animal_id)
                else:
                    animal.mother = None
            else:
                animal.mother = None
        
        # Handle father relationship
        current_father_id = animal.father.animal_id if hasattr(animal.father, 'animal_id') else animal.father
        if father_id != str(current_father_id):
            print(f"Changing father from {current_father_id} to {father_id}")
            # Remove from old father's children if exists
            if animal.father:
                old_father = current_colony.get_animal_by_id(current_father_id)
                if old_father:
                    if hasattr(old_father.children, 'remove'):
                        if animal.animal_id in old_father.children:
                            old_father.children.remove(animal.animal_id)
            
            # Set new father
            if father_id and father_id != "None":
                new_father = current_colony.get_animal_by_id(father_id)
                if new_father:
                    animal.father = new_father
                    if animal.animal_id not in new_father.children:
                        new_father.children.append(animal.animal_id)
                else:
                    animal.father = None
            else:
                animal.father = None
        
        # Save the colony
        save_colony(current_colony, current_colony.name)
        
        # If it was a JSON request, return JSON response
        if request.is_json:
            return jsonify({'success': True})
        # Otherwise redirect back to colony view
        else:
            return redirect(url_for('view_colony'))
    
    except Exception as e:
        print(f"Error in edit_animal: {str(e)}")
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 400
        else:
            flash(f"Error updating animal: {str(e)}", 'error')
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

@app.route('/delete_colony/<name>', methods=['POST'])
def delete_colony(name):
    """Delete a colony file"""
    # Ensure the colonies directory exists
    if not os.path.exists('colonies'):
        return "Error: Colonies directory not found", 404
    
    colony_path = os.path.join('colonies', f'{name}.json')
    
    # Check if the file exists
    if not os.path.exists(colony_path):
        return "Error: Colony file not found", 404
    
    try:
        # If this is the currently loaded colony, clear it
        global current_colony
        if current_colony and current_colony.name == name:
            current_colony = None
        
        # Delete the file
        os.remove(colony_path)
        print(f"Deleted colony: {name}")
        
        return redirect(url_for('list_colonies'))
    except Exception as e:
        print(f"Error deleting colony: {str(e)}")
        return f"Error deleting colony: {str(e)}", 500

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

@app.route('/tree')
def tree_visualization():
    """Open the tree visualization in a new tab"""
    try:
        logger.debug("Opening tree visualization")
        if not current_colony:
            logger.warning("No colony loaded")
            flash("No colony loaded", 'error')
            return redirect(url_for('colonies'))
        
        # Start the Dash server in a separate thread if it's not already running
        from tree_visualization import run_dash_server
        run_dash_server(current_colony)
        
        # Redirect to the Dash app URL
        return redirect('http://127.0.0.1:8050')
    except Exception as e:
        logger.error(f"Error opening tree visualization: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Error opening tree visualization: {str(e)}", 'error')
        return redirect(url_for('view_colony'))

@app.route('/add_cage', methods=['GET', 'POST'])
def add_cage():
    """Add a new cage with multiple animals to the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            cage_id = data.get('cage_id')
            num_animals = int(data.get('num_animals', 1))
            sex = data.get('sex')
            genotype = data.get('genotype')
            dob = datetime.strptime(data.get('dob'), '%Y-%m-%d')
            date_weaned = None
            if data.get('date_weaned'):
                date_weaned = datetime.strptime(data.get('date_weaned'), '%Y-%m-%d')
            mother_id = data.get('mother_id')
            father_id = data.get('father_id')
            notes = data.get('notes')
            
            # Get parent objects if IDs provided
            mother = None
            if mother_id:
                mother = current_colony.get_animal(mother_id)
                
            father = None
            if father_id:
                father = current_colony.get_animal(father_id)
            
            # Create the specified number of animals
            created_animals = []
            for i in range(1, num_animals + 1):
                # Generate animal ID based on cage ID
                animal_id = f"{cage_id}_{i}"
                
                # Check if an animal with this ID already exists
                if current_colony.get_animal(animal_id):
                    return jsonify({
                        'success': False, 
                        'error': f'Animal with ID {animal_id} already exists'
                    })
                
                # Create the animal
                animal = Animal(
                    animal_id=animal_id,
                    sex=sex,
                    genotype=genotype,
                    dob=dob,
                    mother=mother,
                    father=father,
                    notes=notes,
                    cage_id=cage_id,
                    date_weaned=date_weaned
                )
                
                current_colony.add_animal(animal)
                created_animals.append(animal_id)
            
            # Save the colony after adding the animals
            try:
                save_colony(current_colony, current_colony.name)
                print(f"Saved colony after adding cage {cage_id} with {num_animals} animals")
                
                # Return success with list of created animal IDs
                return jsonify({
                    'success': True,
                    'message': f'Created {num_animals} animals in cage {cage_id}',
                    'animals': created_animals
                })
            except Exception as save_error:
                print(f"Error saving colony: {str(save_error)}")
                return jsonify({
                    'success': False,
                    'error': f'Error saving colony: {str(save_error)}'
                })
            
        except Exception as e:
            print(f"Error adding cage: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            })
    
    return render_template('add_cage.html', colony=current_colony)

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
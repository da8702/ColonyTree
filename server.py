from flask import Flask, render_template, send_file, Response, request, jsonify, redirect, url_for, session, flash
from flask.sessions import SecureCookieSessionInterface, SecureCookieSession
import os
import json
import csv
import sys
import glob
import time
import traceback
from datetime import date, datetime, timedelta
from random import randint, choice, random, seed
from threading import Thread
import webbrowser
import requests
import subprocess
import pickle
import base64
from models import Animal, Colony
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a custom session interface to handle colony objects
class CustomSessionInterface(SecureCookieSessionInterface):
    def open_session(self, app, request):
        s = SecureCookieSession()
        return s

    def save_session(self, app, session, response):
        # We'll handle colony objects specially
        # Only store IDs or other simple data in session, not the full colony object
        # This helps avoid pickle serialization issues
        if 'colony' in session:
            colony = session['colony']
            if isinstance(colony, Colony):
                # Store minimal colony info
                session['colony_name'] = colony.name
                session['has_colony'] = True
                # Remove the actual colony object from session
                del session['colony']
        return super().save_session(app, session, response)

# Create Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Required for flash messages
# Use our custom session interface
app.session_interface = CustomSessionInterface()

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
        'animals': [],
        'breeder_cages': colony.breeder_cages
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
            try:
                mother = next((a for a in colony.animals if a.animal_id == animal_data['mother_id']), None)
                if mother:
                    animal.mother = mother
                else:
                    print(f"Warning: Mother animal with ID {animal_data['mother_id']} not found for animal {animal.animal_id}")
            except Exception as e:
                print(f"Error setting mother for animal {animal.animal_id}: {str(e)}")
        
        if animal_data['father_id']:
            try:
                father = next((a for a in colony.animals if a.animal_id == animal_data['father_id']), None)
                if father:
                    animal.father = father
                else:
                    print(f"Warning: Father animal with ID {animal_data['father_id']} not found for animal {animal.animal_id}")
            except Exception as e:
                print(f"Error setting father for animal {animal.animal_id}: {str(e)}")
    
    # Load breeder cages if present
    colony.breeder_cages = data.get('breeder_cages', [])
    # Ensure each breeder cage dict has a litters list
    for bc in colony.breeder_cages:
        if 'litters' not in bc:
            bc['litters'] = []
    return colony

@app.before_request
def before_request():
    """Log debugging info before each request"""
    # Debug logging removed for production
    pass

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
    global current_colony
    if request.method == 'POST':
        name = request.form['name']
        current_colony = Colony(name)
        
        # Store colony name in session
        session['colony_name'] = name
        session['has_colony'] = True
        print(f"Created new colony '{name}' and stored name in session")
        
        return redirect(url_for('view_colony'))
    return render_template('new_colony.html')

@app.route('/colony/load/<name>')
def load_colony_route(name):
    """Load a specific colony"""
    global current_colony
    print(f"Attempting to load colony: {name}")
    
    try:
        print(f"Looking for colony file: colonies/{name}.json")
        if not os.path.exists(f'colonies/{name}.json'):
            print(f"Colony file not found: colonies/{name}.json")
            return f"Error: Colony file colonies/{name}.json not found", 404
            
        current_colony = load_colony(name)
        # Ensure the colony name matches the file name
        current_colony.name = name
        
        # For session, just store the colony name
        session['colony_name'] = name
        session['has_colony'] = True
        print(f"Successfully loaded colony '{name}' with {len(current_colony.animals)} animals")
        print(f"Stored colony name '{name}' in session")
        
        # Extra debugging - what routes we have available
        print(f"Available routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule}")
        
        return redirect(url_for('view_colony'))
    except Exception as e:
        print(f"Error loading colony: {str(e)}")
        traceback.print_exc()
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
    """View the current colony - redirects to Animals view"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    return redirect(url_for('view_animals'))

@app.route('/colony/animals')
def view_animals():
    """View the animals in the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    return render_template('animals_view.html', colony=current_colony)

@app.route('/colony/cages')
def view_cages():
    """View the cages in the current colony"""
    global current_colony
    
    if not current_colony:
        print("No colony loaded, redirecting to colony list")
        return redirect(url_for('list_colonies'))
    
    has_colony_in_session = session.get('has_colony', False)
    colony_name_in_session = session.get('colony_name', 'None')
    print(f"Rendering cages view with colony: {current_colony.name}")
    print(f"Colony in session: {has_colony_in_session}, name: {colony_name_in_session}")
    # Debug: print all animal IDs and cage assignments
    print("DEBUG: Animals and their cages:")
    for a in current_colony.animals:
        print(f"  {a.animal_id}: cage_id={a.cage_id}, sex={a.sex}, dob={a.dob}")
    
    # Pass extra debug info to the template
    template_data = {
        'colony': current_colony,
        'has_colony_in_session': has_colony_in_session,
        'debug_info': {
            'current_colony_name': current_colony.name,
            'colony_name_in_session': colony_name_in_session,
            'names_match': current_colony.name == colony_name_in_session if has_colony_in_session else False
        }
    }
    
    return render_template('cages_view.html', **template_data)

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
@app.route('/visualization/<vis_type>')
def visualization(vis_type=None):
    """Serve the visualization page"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    # Default to animal visualization if type not specified
    if vis_type not in ['animals', 'cages']:
        vis_type = 'animals'
        
    return render_template('visualization.html', colony=current_colony, vis_type=vis_type)

@app.route('/api/colony')
@app.route('/api/colony/<data_type>')
def get_colony_data(data_type=None):
    """Get current colony data for visualization"""
    if not current_colony:
        return jsonify({'error': 'No colony loaded'}), 404
    
    # Default to animal data if type not specified
    if data_type not in ['animals', 'cages']:
        data_type = 'animals'
    
    data = {
        'name': current_colony.name,
        'type': data_type,
        'animals': []
    }
    
    # Always include basic animal data
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
    
    # For cage visualization, add cage data
    if data_type == 'cages':
        # Get unique cages
        unique_cages = {}
        for animal in current_colony.animals:
            if animal.cage_id and animal.cage_id not in unique_cages:
                unique_cages[animal.cage_id] = {
                    'cage_id': animal.cage_id,
                    'animals': []
                }
            
            if animal.cage_id:
                unique_cages[animal.cage_id]['animals'].append(animal.animal_id)
        
        data['cages'] = list(unique_cages.values())
        # Include breeder cages and their litters for cage visualization
        data['breeder_cages'] = current_colony.breeder_cages
        return jsonify(data)
    
    return jsonify(data)

@app.route('/colony/rename', methods=['POST'])
def rename_colony():
    """Rename the current colony"""
    global current_colony
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    new_name = request.form.get('new_name')
    if not new_name:
        return "Error: New name is required", 400
    
    print(f"Renaming colony from '{current_colony.name}' to '{new_name}'")
    current_colony.name = new_name
    
    # Update the colony name in session
    session['colony_name'] = new_name
    session['has_colony'] = True
    print(f"Updated colony name in session to '{new_name}'")
    
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
            if animal.mother and animal in animal.mother.children:
                try:
                    animal.mother.children.remove(animal)
                except ValueError:
                    print(f"Warning: could not remove {animal.animal_id} from previous mother's children list")
            
            if animal.father and animal in animal.father.children:
                try:
                    animal.father.children.remove(animal)
                except ValueError:
                    print(f"Warning: could not remove {animal.animal_id} from previous father's children list")
            
            # Remove references to this animal as a parent from other animals
            for other_animal in current_colony.animals:
                if other_animal.mother and other_animal.mother.animal_id == animal_id:
                    print(f"Removing parent reference: {other_animal.animal_id}'s mother was {animal_id}")
                    other_animal.mother = None
                
                if other_animal.father and other_animal.father.animal_id == animal_id:
                    print(f"Removing parent reference: {other_animal.animal_id}'s father was {animal_id}")
                    other_animal.father = None
            
            # Remove the animal from the colony
            current_colony.animals.remove(animal)
            
            # Save the colony after deletion
            save_colony(current_colony, current_colony.name)
            print(f"Deleted animal {animal_id} from colony {current_colony.name}")
        else:
            print(f"Animal {animal_id} not found in colony {current_colony.name}")
    except Exception as e:
        print(f"Error deleting animal: {str(e)}")
        traceback.print_exc()
    
    return redirect(url_for('view_animals'))

@app.route('/edit_animal/<animal_id>', methods=['POST'])
def edit_animal(animal_id):
    """Edit an existing animal's properties"""
    global current_colony
    
    print(f"Edit animal request received for animal ID: {animal_id}")
    print(f"Request content type: {request.content_type}")
    print(f"Request data: {request.data}")
    
    if not current_colony:
        print("Error: No colony loaded (current_colony is None)")
        return jsonify({'success': False, 'error': 'No colony selected'}), 400
    
    try:
        # Check if the request is JSON or form data
        if request.is_json:
            data = request.get_json()
            print(f"Parsed JSON data: {data}")
        else:
            print("Request is not JSON format")
            try:
                # Try to parse the request data as JSON manually
                data = json.loads(request.data)
                print(f"Manually parsed JSON data: {data}")
            except Exception as e:
                print(f"Failed to parse request data: {e}")
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
                print(f"Form data: {data}")
        
        if not data:
            print("No data provided in request")
            return jsonify({'success': False, 'error': 'No data provided'}), 400
            
        print(f"Processing edit for animal: {animal_id}")
            
        original_id = data.get('original_id', animal_id)  # Use the path parameter as fallback
        
        # Get the animal using the original ID
        animal = current_colony.get_animal_by_id(original_id)
        if not animal:
            print(f"Animal with ID {original_id} not found")
            return jsonify({'success': False, 'error': f'Animal with ID {original_id} not found'}), 404
            
        # Get the new values from the request
        new_id = data.get('animal_id')
        sex = data.get('sex')
        genotype = data.get('genotype')
        dob_str = data.get('dob')
        date_weaned_str = data.get('date_weaned')
        cage_id = data.get('cage_id')
        mother_id = data.get('mother_id')
        father_id = data.get('father_id')
        notes = data.get('notes', '')
        
        print(f"New values: id={new_id}, sex={sex}, genotype={genotype}, dob={dob_str}, date_weaned={date_weaned_str}, cage={cage_id}, mother={mother_id}, father={father_id}")
        
        # Parse dates
        dob = None
        if dob_str:
            try:
                dob = date.fromisoformat(dob_str)
            except ValueError:
                print(f"Invalid date of birth format: {dob_str}")
                return jsonify({'success': False, 'error': f'Invalid date of birth format: {dob_str}'}), 400
                
        date_weaned = None
        if date_weaned_str:
            try:
                date_weaned = date.fromisoformat(date_weaned_str)
            except ValueError:
                print(f"Invalid date weaned format: {date_weaned_str}")
                return jsonify({'success': False, 'error': f'Invalid date weaned format: {date_weaned_str}'}), 400
        
        # Update the animal ID if it changed
        if new_id and new_id != original_id:
            print(f"Changing animal ID from {original_id} to {new_id}")
            # Check if the new ID already exists
            if current_colony.get_animal_by_id(new_id):
                print(f"Animal with ID {new_id} already exists")
                return jsonify({'success': False, 'error': f'Animal with ID {new_id} already exists'}), 400
            animal.animal_id = new_id
            
        # Update other properties
        if sex:
            animal.sex = sex
        if genotype:
            animal.genotype = genotype
        if dob:
            animal.dob = dob
        if date_weaned:
            animal.date_weaned = date_weaned
        if cage_id is not None:  # Allow empty cage_id to clear existing cage
            animal.cage_id = cage_id
        if notes is not None:  # Allow empty notes to clear existing notes
            animal.notes = notes
            
        # Update mother if changed
        old_mother_id = animal.mother.animal_id if animal.mother else None
        if mother_id != old_mother_id:
            print(f"Changing mother from {old_mother_id} to {mother_id}")
            # If there was a previous mother, remove this animal from her children
            if animal.mother:
                try:
                    animal.mother.children.remove(animal)
                except ValueError:
                    print(f"Warning: could not remove {animal.animal_id} from previous mother's children list")
            
            # Set the new mother
            if mother_id:
                mother = current_colony.get_animal_by_id(mother_id)
                if mother:
                    animal.mother = mother
                    if animal not in mother.children:
                        mother.children.append(animal)
                else:
                    print(f"Mother with ID {mother_id} not found")
            else:
                animal.mother = None
                
        # Update father if changed
        old_father_id = animal.father.animal_id if animal.father else None
        if father_id != old_father_id:
            print(f"Changing father from {old_father_id} to {father_id}")
            # If there was a previous father, remove this animal from his children safely
            if animal.father and animal in animal.father.children:
                try:
                    animal.father.children.remove(animal)
                except Exception as e:
                    print(f"Warning: failed to remove {animal.animal_id} from old father's children: {e}")
            
            # Set the new father
            if father_id:
                father = current_colony.get_animal_by_id(father_id)
                if father:
                    animal.father = father
                    if animal not in father.children:
                        father.children.append(animal)
                else:
                    print(f"Father with ID {father_id} not found")
            else:
                animal.father = None
        
        # Save the colony
        print(f"Saving colony after updating animal {animal.animal_id}")
        save_colony(current_colony, current_colony.name)
        
        print(f"Successfully updated animal {animal.animal_id}")
        
        # Check if the request is for form data (not JSON) and redirect to animals view
        if request.content_type and 'application/json' not in request.content_type:
            return redirect(url_for('view_animals'))
            
        # For API calls, return JSON response
        return jsonify({
            'success': True,
            'message': f'Successfully updated animal {animal.animal_id}'
        })
        
    except Exception as e:
        print(f"Error in edit_animal: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 400

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
        # Determine if this is an API (JSON) call or a form submission
        is_api = request.is_json
        try:
            if is_api:
                data = request.get_json()
            else:
                data = request.form
            
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
            breeder_id = data.get('breeder_cage_id')  # for litters
            
            # Get parent objects
            mother = current_colony.get_animal(mother_id) if mother_id else None
            father = current_colony.get_animal(father_id) if father_id else None
            
            # Create animals in the new cage
            created_animals = []
            for i in range(1, num_animals + 1):
                animal_id = f"{cage_id}_{i}"
                if current_colony.get_animal(animal_id):
                    raise ValueError(f"Animal with ID {animal_id} already exists")
                animal = Animal(animal_id, sex, genotype, dob, mother, father, notes, cage_id, date_weaned)
                current_colony.add_animal(animal)
                created_animals.append(animal_id)
            
            # Save after creating the cage
            save_colony(current_colony, current_colony.name)
            print(f"Saved colony after adding cage {cage_id} with {num_animals} animals")
            
            # If this is a litter addition, update the breeder cage entry
            if breeder_id:
                bc = next((bc for bc in current_colony.breeder_cages if bc['cage_id'] == breeder_id), None)
                if bc is not None:
                    bc['litters'].append(cage_id)
                    save_colony(current_colony, current_colony.name)
                    print(f"Added litter {cage_id} to breeder cage {breeder_id}")
            
            # Return based on request type
            if is_api:
                return jsonify({'success': True, 'message': f'Created {num_animals} animals in cage {cage_id}', 'animals': created_animals})
            else:
                return redirect(url_for('view_cages'))
        except Exception as e:
            print(f"Error adding cage: {e}")
            if is_api:
                return jsonify({'success': False, 'error': str(e)})
            else:
                flash(str(e), 'error')
                return redirect(url_for('view_cages'))
    
    return render_template('add_cage.html', colony=current_colony)

@app.route('/delete_cage', methods=['POST'])
def delete_cage():
    """Delete a cage and all animals in it from the current colony"""
    if not current_colony:
        return redirect(url_for('list_colonies'))
    
    cage_id = request.form.get('cage_id')
    if not cage_id:
        print("No cage_id provided")
        return redirect(url_for('view_cages'))
    
    try:
        print(f"Attempting to delete cage: {cage_id}")
        # Find all animals in the cage
        animals_to_delete = [animal for animal in current_colony.animals if animal.cage_id == cage_id]
        
        if not animals_to_delete:
            print(f"No animals found in cage {cage_id}")
            return redirect(url_for('view_cages'))
        
        # Remove each animal
        for animal in animals_to_delete:
            print(f"Removing animal: {animal.animal_id}")
            # Remove parent-child relationships
            if animal.mother and animal in animal.mother.children:
                try:
                    animal.mother.children.remove(animal)
                except ValueError:
                    print(f"Warning: could not remove {animal.animal_id} from previous mother's children list")
            
            if animal.father and animal in animal.father.children:
                try:
                    animal.father.children.remove(animal)
                except ValueError:
                    print(f"Warning: could not remove {animal.animal_id} from previous father's children list")
            
            # Remove the animal from the colony
            current_colony.animals.remove(animal)
        
        # Save the colony after deletion
        save_colony(current_colony, current_colony.name)
        print(f"Deleted cage {cage_id} with {len(animals_to_delete)} animals from colony {current_colony.name}")
        
    except Exception as e:
        print(f"Error deleting cage: {str(e)}")
        traceback.print_exc()
    
    return redirect(url_for('view_cages'))

@app.route('/edit_cage', methods=['POST'])
def edit_cage():
    """Update all animals in a cage with the specified properties"""
    global current_colony
    
    print("\n----- EDIT CAGE REQUEST RECEIVED -----")
    print(f"Request method: {request.method}")
    print(f"Content type: {request.content_type}")
    print(f"Request data: {request.data}")
    print(f"Request form: {request.form}")
    
    if not current_colony:
        print("No active colony found, trying to recover from session")
        # Try to recover the colony from session if possible
        colony_name = session.get('colony_name')
        print(f"Colony name from session: {colony_name}")
        
        if colony_name and os.path.exists(f'colonies/{colony_name}.json'):
            try:
                print(f"Loading colony from file: colonies/{colony_name}.json")
                current_colony = load_colony(colony_name)
                print(f"Successfully loaded colony with {len(current_colony.animals)} animals")
            except Exception as e:
                print(f"Failed to load colony: {e}")
                traceback.print_exc()
                return jsonify({'success': False, 'error': 'Failed to load colony. Please reload your colony.'}), 400
        else:
            print("No colony in session or colony file not found")
            return jsonify({'success': False, 'error': 'No colony selected or colony not found. Please select a colony.'}), 400
    else:
        print(f"Using active colony: {current_colony.name} with {len(current_colony.animals)} animals")
    
    try:
        # Get data from request
        data = None
        
        if request.is_json:
            print("Request is JSON format")
            data = request.get_json()
            print(f"Parsed JSON data: {data}")
        else:
            print("Request is not JSON format, trying alternative parsing")
            try:
                # Try to parse the request data as JSON manually
                request_data = request.data.decode('utf-8') if hasattr(request.data, 'decode') else str(request.data)
                print(f"Raw request data: {request_data}")
                data = json.loads(request_data)
                print(f"Manually parsed JSON data: {data}")
            except Exception as e:
                print(f"Failed to parse as JSON: {e}")
                # Fall back to form data
                data = request.form.to_dict()
                print(f"Form data: {data}")
                
                # If still no data, try to parse the raw request
                if not data and request_data:
                    try:
                        print("Trying to parse as URL-encoded data")
                        import urllib.parse
                        parsed_data = urllib.parse.parse_qs(request_data)
                        data = {k: v[0] for k, v in parsed_data.items()}
                        print(f"URL-encoded data: {data}")
                    except Exception as e:
                        print(f"Failed to parse as URL-encoded: {e}")
        
        if not data:
            print("ERROR: No data could be extracted from request")
            return jsonify({'success': False, 'error': 'No data provided or could not parse request data'}), 400
            
        # Check if we should skip straight to redirect for non-AJAX requests
        view_response = data.get('view_response', False)
        print(f"View response flag: {view_response}")
            
        cage_id = data.get('cage_id')
        if not cage_id:
            print("ERROR: No cage ID provided in request data")
            return jsonify({'success': False, 'error': 'No cage ID provided'}), 400

        # Find all animals in the specified cage
        print(f"Looking for animals in cage: {cage_id}")
        animals_in_cage = [animal for animal in current_colony.animals if animal.cage_id == cage_id]
        print(f"Found {len(animals_in_cage)} animals in cage {cage_id}")
        if not animals_in_cage:
            print(f"ERROR: No animals found in cage {cage_id}")
            return jsonify({'success': False, 'error': f'No animals found in cage {cage_id}'}), 404
        
        # Update cage ID for each animal
        new_cage_id = data.get('new_cage_id')
        if new_cage_id and new_cage_id != cage_id:
            print(f"Updating cage ID from {cage_id} to {new_cage_id}")
            for animal in animals_in_cage:
                old_id = animal.animal_id
                suffix = animal.animal_id.split('_', 1)[1] if '_' in animal.animal_id else '1'
                animal.animal_id = f"{new_cage_id}_{suffix}"
                animal.cage_id = new_cage_id
                print(f"  Updated animal ID from {old_id} to {animal.animal_id}")
            print(f"Updated cage ID for {len(animals_in_cage)} animals")
        
        # Get the properties to update
        sex = data.get('sex')
        genotype = data.get('genotype')
        dob_str = data.get('dob')
        date_weaned_str = data.get('date_weaned')
        notes = data.get('notes', '')
        
        print(f"Properties to update - sex: {sex}, genotype: {genotype}, dob: {dob_str}, weaned: {date_weaned_str}, notes: {notes}")
        
        # Convert date strings to date objects
        dob = None
        if dob_str:
            try:
                dob = date.fromisoformat(dob_str)
                print(f"Parsed DOB: {dob}")
            except ValueError as e:
                print(f"Error parsing DOB: {e}")
                return jsonify({'success': False, 'error': f'Invalid date of birth format: {dob_str}'}), 400
                
        date_weaned = None
        if date_weaned_str:
            try:
                date_weaned = date.fromisoformat(date_weaned_str)
                print(f"Parsed date weaned: {date_weaned}")
            except ValueError as e:
                print(f"Error parsing date weaned: {e}")
                return jsonify({'success': False, 'error': f'Invalid date weaned format: {date_weaned_str}'}), 400
        
        # Update each animal in the cage
        for animal in animals_in_cage:
            print(f"Updating animal: {animal.animal_id}")
            if sex:
                print(f"  Changing sex from {animal.sex} to {sex}")
                animal.sex = sex
            if genotype:
                print(f"  Changing genotype from {animal.genotype} to {genotype}")
                animal.genotype = genotype
            if dob:
                print(f"  Changing DOB from {animal.dob} to {dob}")
                animal.dob = dob
            if date_weaned:
                old_date = getattr(animal, 'date_weaned', None)
                print(f"  Changing date weaned from {old_date} to {date_weaned}")
                animal.date_weaned = date_weaned
            if notes is not None:  # Allow empty notes to clear existing notes
                old_notes = getattr(animal, 'notes', '')
                print(f"  Changing notes from '{old_notes}' to '{notes}'")
                animal.notes = notes
        
        # Save the colony
        print(f"Saving colony {current_colony.name} with updated animals")
        save_colony(current_colony, current_colony.name)
        print("Colony saved successfully")
        
        # For normal form submission, redirect instead of returning JSON
        if view_response and not request.is_json:
            print("Redirecting to view_cages")
            return redirect(url_for('view_cages'))
        
        # Otherwise return JSON response
        print("Returning JSON success response")
        response = {
            'success': True,
            'message': f'Updated {len(animals_in_cage)} animals in cage {cage_id}',
            'colony_name': current_colony.name,
            'animals_updated': [animal.animal_id for animal in animals_in_cage],
            'redirect_url': url_for('view_cages')
        }
        print(f"Response: {response}")
        return jsonify(response)
    
    except Exception as e:
        # Log error but don't expose all details to client
        print(f"ERROR in edit_cage: {str(e)}")
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500

# Add breeder cage route
@app.route('/add_breeder_cage', methods=['GET', 'POST'])
def add_breeder_cage():
    """Add a new breeder cage with specified parents and optional date mated/notes"""
    global current_colony
    if not current_colony:
        return redirect(url_for('list_colonies'))

    if request.method == 'POST':
        try:
            data = request.get_json()
            cage_id = data.get('cage_id')
            mother_id = data.get('mother_id')
            father_id = data.get('father_id')
            date_mated = data.get('date_mated')
            notes = data.get('notes')

            # Validate required fields
            if not cage_id or not mother_id or not father_id:
                return jsonify({'success': False, 'error': 'Cage ID, mother ID, and father ID are required'}), 400

            mother = current_colony.get_animal(mother_id)
            father = current_colony.get_animal(father_id)
            if not mother or mother.sex != 'F':
                return jsonify({'success': False, 'error': f'Mother {mother_id} not found or not female'}), 400
            if not father or father.sex != 'M':
                return jsonify({'success': False, 'error': f'Father {father_id} not found or not male'}), 400

            # Append breeder cage entry
            breeder_entry = {
                'cage_id': cage_id,
                'mother_id': mother_id,
                'father_id': father_id,
                'date_mated': date_mated,
                'notes': notes,
                'litters': []
            }
            current_colony.breeder_cages.append(breeder_entry)

            # Update parents' cage assignment
            mother.cage_id = cage_id
            father.cage_id = cage_id

            save_colony(current_colony, current_colony.name)
            return jsonify({'success': True})
        except Exception as e:
            print(f"Error adding breeder cage: {e}")
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    # GET request
    return render_template('add_breeder_cage.html', colony=current_colony)

# Add edit breeder cage handling route
@app.route('/edit_breeder_cage', methods=['POST'])
def edit_breeder_cage():
    """Edit an existing breeder cage's properties"""
    global current_colony
    if not current_colony:
        return redirect(url_for('list_colonies'))

    # Get form values
    original_cage_id = request.form.get('original_cage_id')
    new_cage_id = request.form.get('new_cage_id') or original_cage_id
    mother_id = request.form.get('mother_id')
    father_id = request.form.get('father_id')
    date_mated = request.form.get('date_mated') or None
    notes = request.form.get('notes') or ''

    for bc in current_colony.breeder_cages:
        if bc['cage_id'] == original_cage_id:
            # Rename breeder cage if needed
            if new_cage_id and new_cage_id != original_cage_id:
                # Prevent duplicates
                if any(b['cage_id'] == new_cage_id for b in current_colony.breeder_cages):
                    # Skip renaming if already exists
                    pass
                else:
                    bc['cage_id'] = new_cage_id
                    # Update parent animal cage_id
                    parent_mom = current_colony.get_animal(bc['mother_id'])
                    parent_dad = current_colony.get_animal(bc['father_id'])
                    if parent_mom:
                        parent_mom.cage_id = new_cage_id
                    if parent_dad:
                        parent_dad.cage_id = new_cage_id
            # Update other fields
            bc['mother_id'] = mother_id
            bc['father_id'] = father_id
            bc['date_mated'] = date_mated
            bc['notes'] = notes
            break

    # Save changes
    save_colony(current_colony, current_colony.name)

    # Redirect back to cages view
    return redirect(url_for('view_cages'))

# Add delete breeder cage route
@app.route('/delete_breeder_cage', methods=['POST'])
def delete_breeder_cage():
    """Delete a breeder cage entry and unassign parents"""
    global current_colony
    if not current_colony:
        return redirect(url_for('list_colonies'))
    cage_id = request.form.get('cage_id')
    if not cage_id:
        print("No breeder cage_id provided for deletion")
        return redirect(url_for('view_cages'))
    try:
        bc_to_delete = next((bc for bc in current_colony.breeder_cages if bc['cage_id'] == cage_id), None)
        if bc_to_delete:
            current_colony.breeder_cages.remove(bc_to_delete)
            # Unassign parents from this breeder cage
            mother = current_colony.get_animal(bc_to_delete['mother_id'])
            father = current_colony.get_animal(bc_to_delete['father_id'])
            if mother:
                mother.cage_id = None
            if father:
                father.cage_id = None
            save_colony(current_colony, current_colony.name)
            print(f"Deleted breeder cage {cage_id}")
        else:
            print(f"Breeder cage {cage_id} not found")
    except Exception as e:
        print(f"Error deleting breeder cage: {e}")
        traceback.print_exc()
    return redirect(url_for('view_cages'))

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
import dash
from dash import html, dcc
import dash_cytoscape as cyto
import json
import os
from datetime import date

# Load Cytoscape extension
cyto.load_extra_layouts()

# Initialize the Dash app
app = dash.Dash(__name__)

# Define the layout
app.layout = html.Div([
    html.H1("Animal Family Tree Visualization"),
    
    # Colony selector
    html.Div([
        html.Label("Select Colony:"),
        dcc.Dropdown(
            id='colony-selector',
            options=[],  # Will be populated dynamically
            placeholder="Select a colony..."
        )
    ], style={'width': '50%', 'margin': '20px'}),
    
    # Cytoscape graph
    cyto.Cytoscape(
        id='cytoscape',
        layout={'name': 'dagre', 'rankDir': 'LR'},
        style={'width': '100%', 'height': '80vh'},
        elements=[],
        stylesheet=[
            {
                'selector': 'node',
                'style': {
                    'content': 'data(label)',
                    'text-wrap': 'wrap',
                    'text-max-width': '80px',
                    'font-size': '12px',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'background-color': '#ffffff',
                    'border-width': 1,
                    'border-color': '#000000',
                    'shape': 'ellipse'
                }
            },
            {
                'selector': 'node[sex="M"]',
                'style': {
                    'shape': 'rectangle'
                }
            },
            {
                'selector': 'edge',
                'style': {
                    'width': 1,
                    'line-color': '#666666',
                    'target-arrow-color': '#666666',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier'
                }
            }
        ]
    )
])

def load_colony(filename):
    """Load colony from JSON file"""
    with open(filename, 'r') as f:
        data = json.load(f)
    return data

def create_elements(colony_data):
    """Create Cytoscape elements from colony data"""
    elements = []
    
    # Add nodes
    for animal in colony_data['animals']:
        node = {
            'data': {
                'id': animal['animal_id'],
                'label': f"{animal['animal_id']}\n{animal['genotype']}",
                'sex': animal['sex']
            }
        }
        elements.append(node)
    
    # Add edges
    for animal in colony_data['animals']:
        if animal['mother_id']:
            edge = {
                'data': {
                    'source': animal['mother_id'],
                    'target': animal['animal_id']
                }
            }
            elements.append(edge)
        if animal['father_id']:
            edge = {
                'data': {
                    'source': animal['father_id'],
                    'target': animal['animal_id']
                }
            }
            elements.append(edge)
    
    return elements

@app.callback(
    dash.Output('colony-selector', 'options'),
    dash.Input('colony-selector', 'value')
)
def update_colony_options(value):
    """Update colony selector options"""
    if not os.path.exists('colonies'):
        return []
    
    colonies = [f for f in os.listdir('colonies') if f.endswith('.json')]
    return [{'label': f[:-5].replace('_', ' ').title(), 'value': f} for f in colonies]

@app.callback(
    dash.Output('cytoscape', 'elements'),
    dash.Input('colony-selector', 'value')
)
def update_graph(selected_colony):
    """Update the graph when a colony is selected"""
    if not selected_colony:
        return []
    
    try:
        colony_data = load_colony(f"colonies/{selected_colony}")
        return create_elements(colony_data)
    except Exception as e:
        print(f"Error loading colony: {e}")
        return []

if __name__ == '__main__':
    app.run(debug=False, port=8050) 
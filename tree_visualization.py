import dash
from dash import html, dcc
import dash_cytoscape as cyto
import json
import os
from datetime import date
import plotly.graph_objects as go
import networkx as nx
from models import Colony, Animal

# Load Cytoscape extension
cyto.load_extra_layouts()

# Initialize the Dash app
app = dash.Dash(__name__)

# Global variable to store the current colony
current_colony = None

def update_colony(colony):
    """Update the current colony in the Dash app"""
    print("\n=== Updating Dash Colony ===")
    global current_colony
    current_colony = colony
    print(f"Updated colony: {colony.name}")
    print(f"Number of animals: {len(colony.animals)}")
    # Force a refresh of the graph
    if app.layout:
        print("Updating graph...")
        app.layout['family-tree'].figure = create_family_tree()
        print("Graph updated")

def create_family_tree():
    print("\n=== Creating Family Tree ===")
    if not current_colony:
        print("No colony available")
        return go.Figure()
    
    print(f"Creating tree for colony: {current_colony.name}")
    print(f"Number of animals: {len(current_colony.animals)}")
        
    # Create a directed graph
    G = nx.DiGraph()
    
    # Add nodes with attributes
    for animal in current_colony.animals:
        G.add_node(animal.animal_id,
                  sex=animal.sex,
                  genotype=animal.genotype)
    
    # Add edges for parent-child relationships
    for animal in current_colony.animals:
        if animal.mother:
            G.add_edge(animal.mother.animal_id, animal.animal_id)
        if animal.father:
            G.add_edge(animal.father.animal_id, animal.animal_id)
    
    print(f"Created graph with {len(G.nodes())} nodes and {len(G.edges())} edges")
    
    # Create the plot
    pos = nx.spring_layout(G, k=1, iterations=50)
    
    # Create edges
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')
    
    # Create nodes
    node_x = []
    node_y = []
    node_text = []
    node_color = []
    
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(f"{node}<br>{G.nodes[node]['genotype']}")
        node_color.append('pink' if G.nodes[node]['sex'] == 'F' else 'lightblue')
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=node_text,
        textposition="top center",
        marker=dict(
            size=20,
            color=node_color,
            line_width=2))
    
    # Create the figure
    fig = go.Figure(data=[edge_trace, node_trace],
                   layout=go.Layout(
                       showlegend=False,
                       hovermode='closest',
                       margin=dict(b=20,l=5,r=5,t=40),
                       title=f"Family Tree - {current_colony.name}",
                       annotations=[dict(
                           text="",
                           showarrow=False,
                           xref="paper", yref="paper",
                           x=0, y=0)],
                       xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                       yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
    
    print("Figure created successfully")
    return fig

# Define the layout
app.layout = html.Div([
    html.H1("Animal Colony Family Tree"),
    dcc.Graph(id='family-tree'),
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # in milliseconds
        n_intervals=0
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
    dash.Output('family-tree', 'figure'),
    dash.Input('interval-component', 'n_intervals')
)
def update_graph(n):
    return create_family_tree()

if __name__ == '__main__':
    app.run(debug=False, port=8050) 
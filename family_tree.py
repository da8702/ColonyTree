import networkx as nx
import matplotlib.pyplot as plt
from datetime import date
from typing import Optional, List
import json
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                            QComboBox, QDateEdit, QMessageBox, QTabWidget,
                            QScrollArea, QFrame, QInputDialog, QFileDialog)
from PyQt5.QtCore import Qt, QDate
import sys
import webbrowser
from threading import Thread
from tree_visualization import app as dash_app
from models import Animal, Colony

class FamilyTreeView(QFrame):
    def __init__(self, colony: Colony):
        super().__init__()
        self.colony = colony
        self.setMinimumSize(800, 600)
        self.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.setLineWidth(1)
        self.update_tree()

    def update_tree(self):
        # Create a directed graph
        G = nx.DiGraph()
        
        # Add nodes with attributes
        for animal in self.colony.animals:
            G.add_node(animal.animal_id,
                      sex=animal.sex,
                      genotype=animal.genotype)
        
        # Add edges for parent-child relationships
        for animal in self.colony.animals:
            if animal.mother:
                G.add_edge(animal.mother.animal_id, animal.animal_id)
            if animal.father:
                G.add_edge(animal.father.animal_id, animal.animal_id)
        
        # Create the plot
        plt.figure(figsize=(15, 10))
        
        # Use hierarchical layout
        pos = nx.spring_layout(G, k=1, iterations=50)
        
        # Draw edges
        nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True, arrowsize=20)
        
        # Draw nodes with different shapes for males and females
        for node in G.nodes():
            x, y = pos[node]
            if G.nodes[node]['sex'] == 'F':
                circle = plt.Circle((x, y), 0.1, facecolor='white', edgecolor='black')
                plt.gca().add_patch(circle)
            else:
                rect = plt.Rectangle((x-0.1, y-0.1), 0.2, 0.2, facecolor='white', edgecolor='black')
                plt.gca().add_patch(rect)
            
            # Add labels with animal ID and genotype
            label = f"{node}\n{G.nodes[node]['genotype']}"
            plt.text(x, y+0.15, label, ha='center', va='center', fontsize=8)
        
        # Set the axis limits with some padding
        plt.xlim(-0.2, 1.2)
        plt.ylim(-0.2, 1.2)
        
        # Hide axes
        plt.axis('off')
        
        # Add title
        plt.title(f"Family Tree - {self.colony.name}", pad=20)
        
        # Save the plot to a temporary file
        plt.savefig('temp_tree.png', bbox_inches='tight', dpi=300)
        plt.close()

class AnimalTreeTab(QWidget):
    def __init__(self, colony: Colony):
        super().__init__()
        self.colony = colony
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Add animal form
        form_layout = QVBoxLayout()
        
        # Animal ID
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Animal ID:"))
        self.id_input = QLineEdit()
        id_layout.addWidget(self.id_input)
        form_layout.addLayout(id_layout)
        
        # Sex
        sex_layout = QHBoxLayout()
        sex_layout.addWidget(QLabel("Sex:"))
        self.sex_input = QComboBox()
        self.sex_input.addItems(["M", "F"])
        sex_layout.addWidget(self.sex_input)
        form_layout.addLayout(sex_layout)
        
        # Genotype
        genotype_layout = QHBoxLayout()
        genotype_layout.addWidget(QLabel("Genotype:"))
        self.genotype_input = QComboBox()
        self.genotype_input.addItems(["Homo (+/+)", "Het (+/-)", "WT (-/-)"])
        genotype_layout.addWidget(self.genotype_input)
        form_layout.addLayout(genotype_layout)
        
        # Date of Birth
        dob_layout = QHBoxLayout()
        dob_layout.addWidget(QLabel("Date of Birth:"))
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate.currentDate())
        dob_layout.addWidget(self.dob_input)
        form_layout.addLayout(dob_layout)
        
        # Parents
        parents_layout = QHBoxLayout()
        parents_layout.addWidget(QLabel("Mother ID:"))
        self.mother_input = QLineEdit()
        parents_layout.addWidget(self.mother_input)
        parents_layout.addWidget(QLabel("Father ID:"))
        self.father_input = QLineEdit()
        parents_layout.addWidget(self.father_input)
        form_layout.addLayout(parents_layout)
        
        # Add button
        add_button = QPushButton("Add Animal")
        add_button.clicked.connect(self.add_animal)
        form_layout.addWidget(add_button)
        
        layout.addLayout(form_layout)
        
        # Family tree view
        self.tree_view = FamilyTreeView(self.colony)
        layout.addWidget(self.tree_view)
        
        self.setLayout(layout)

    def add_animal(self):
        try:
            print("\n=== Adding New Animal ===")
            print(f"Current colony: {self.colony.name}")
            print(f"Current number of animals: {len(self.colony.animals)}")
            
            animal_id = self.id_input.text()
            if not animal_id:
                QMessageBox.warning(self, "Error", "Please enter an Animal ID")
                return
                
            sex = self.sex_input.currentText()
            genotype = self.genotype_input.currentText()
            dob = self.dob_input.date().toPyDate()
            
            # Find parents
            mother_id = self.mother_input.text().strip()
            father_id = self.father_input.text().strip()
            
            mother = next((a for a in self.colony.animals if a.animal_id == mother_id), None) if mother_id else None
            father = next((a for a in self.colony.animals if a.animal_id == father_id), None) if father_id else None
            
            # Create and add animal
            animal = Animal(animal_id, sex, genotype, dob, mother, father)
            self.colony.add_animal(animal)
            
            print(f"Added animal: {animal_id}")
            print(f"New number of animals: {len(self.colony.animals)}")
            
            # Update tree view
            self.tree_view.update_tree()
            
            # Auto-save the colony
            try:
                # Ensure the colonies directory exists
                os.makedirs('colonies', exist_ok=True)
                filename = os.path.join(os.getcwd(), 'colonies', f"{self.colony.name.lower().replace(' ', '_')}.json")
                save_colony(self.colony, filename)
                print(f"Saved colony to: {filename}")
                
                # Update the Dash visualization if it's running
                if hasattr(self.parent(), 'dash_thread') and self.parent().dash_thread and self.parent().dash_thread.is_alive():
                    print("Updating Dash visualization...")
                    dash_app.update_colony(self.colony)
                    print("Dash visualization updated")
                else:
                    print("Dash visualization not running")
            except Exception as save_error:
                print(f"Error saving/updating: {str(save_error)}")
                QMessageBox.warning(self, "Warning", f"Animal added but failed to auto-save: {str(save_error)}")
            
            # Clear inputs
            self.id_input.clear()
            self.mother_input.clear()
            self.father_input.clear()
            
            QMessageBox.information(self, "Success", f"Added animal {animal_id}")
            
        except Exception as e:
            print(f"Error adding animal: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to add animal: {str(e)}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.colonies = {}
        self.dash_thread = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Animal Colony Manager")
        self.setMinimumSize(1000, 800)
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Colony management buttons
        button_layout = QHBoxLayout()
        
        new_colony_btn = QPushButton("New Colony")
        new_colony_btn.clicked.connect(self.new_colony)
        button_layout.addWidget(new_colony_btn)
        
        save_colony_btn = QPushButton("Save Colony")
        save_colony_btn.clicked.connect(self.save_current_colony)
        button_layout.addWidget(save_colony_btn)
        
        load_colony_btn = QPushButton("Load Colony")
        load_colony_btn.clicked.connect(self.load_colony)
        button_layout.addWidget(load_colony_btn)
        
        # Add visualization button
        visualize_btn = QPushButton("Open Tree Visualization")
        visualize_btn.clicked.connect(self.open_visualization)
        button_layout.addWidget(visualize_btn)
        
        layout.addLayout(button_layout)
        
        # Tab widget for colonies
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_colony)
        layout.addWidget(self.tab_widget)

    def new_colony(self):
        name, ok = QInputDialog.getText(self, "New Colony", "Enter colony name:")
        if ok and name:
            colony = Colony(name)
            self.colonies[name] = colony
            tab = AnimalTreeTab(colony)
            self.tab_widget.addTab(tab, name)

    def save_current_colony(self):
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            QMessageBox.warning(self, "Error", "No colony selected")
            return
            
        colony = current_tab.colony
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Colony",
            f"colonies/{colony.name.lower().replace(' ', '_')}.json",
            "JSON files (*.json)"
        )
        
        if filename:
            try:
                save_colony(colony, filename)
                QMessageBox.information(self, "Success", "Colony saved successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save colony: {str(e)}")

    def load_colony(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Colony",
            "colonies",
            "JSON files (*.json)"
        )
        
        if filename:
            try:
                colony = load_colony(filename)
                self.colonies[colony.name] = colony
                tab = AnimalTreeTab(colony)
                self.tab_widget.addTab(tab, colony.name)
                QMessageBox.information(self, "Success", "Colony loaded successfully")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load colony: {str(e)}")

    def close_colony(self, index):
        self.tab_widget.removeTab(index)

    def run_dash_server(self):
        """Run the Dash server"""
        try:
            dash_app.run_server(debug=False, port=8050, use_reloader=False)
        except Exception as e:
            print(f"Dash server error: {str(e)}")

    def open_visualization(self):
        """Open the Dash visualization in the default web browser"""
        print("\n=== Opening Visualization ===")
        current_tab = self.tab_widget.currentWidget()
        if not current_tab:
            QMessageBox.warning(self, "Error", "No colony selected")
            return
            
        # Get the current colony
        current_colony = current_tab.colony
        print(f"Current colony: {current_colony.name}")
        print(f"Number of animals: {len(current_colony.animals)}")
        
        if self.dash_thread is None or not self.dash_thread.is_alive():
            print("Starting new Dash server...")
            # Update the Dash app with the current colony
            dash_app.update_colony(current_colony)
            print("Updated Dash app with current colony")
            
            # Start Dash server in a separate thread
            self.dash_thread = Thread(target=self.run_dash_server)
            self.dash_thread.daemon = True
            self.dash_thread.start()
            print("Started Dash server thread")
            
            # Wait a moment for the server to start
            import time
            time.sleep(2)  # Increased wait time to ensure server starts
            print("Server startup wait complete")
            
            # Open the visualization in the default web browser
            webbrowser.open('http://127.0.0.1:8050')
            print("Opened browser")
        else:
            print("Dash server already running, updating colony...")
            # If the server is already running, update the colony and refresh
            dash_app.update_colony(current_colony)
            print("Updated Dash app with current colony")
            webbrowser.open('http://127.0.0.1:8050')
            print("Opened browser")

def save_colony(colony: Colony, filename: str):
    """Save colony to JSON file"""
    # Ensure the colonies directory exists
    os.makedirs('colonies', exist_ok=True)
    
    # Convert to absolute path if it's a relative path
    if not os.path.isabs(filename):
        filename = os.path.join(os.getcwd(), filename)
    
    with open(filename, 'w') as f:
        json.dump(colony.to_dict(), f, indent=2)

def load_colony(filename: str) -> Colony:
    """Load colony from JSON file"""
    # Convert to absolute path if it's a relative path
    if not os.path.isabs(filename):
        filename = os.path.join(os.getcwd(), filename)
        
    with open(filename, 'r') as f:
        data = json.load(f)
    return Colony.from_dict(data)

def main():
    # Create a directory for saving colonies if it doesn't exist
    if not os.path.exists('colonies'):
        os.makedirs('colonies')
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 
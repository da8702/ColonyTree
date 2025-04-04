# ColonyTree

A web-based application for managing and visualizing animal colonies and their family trees.

## Features

- Create and manage multiple animal colonies
- Add animals with detailed information (ID, sex, genotype, date of birth)
- Track parent-child relationships
- Interactive family tree visualization
- Rename and manage colonies
- Web-based interface for easy access

## Installation

1. Clone the repository:
```bash
git clone https://github.com/da8702/ColonyTree.git
cd ColonyTree
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python server.py
```

2. Open your web browser and navigate to:
- Main application: http://localhost:5000
- Tree visualization: http://localhost:8050

## Project Structure

- `server.py`: Main Flask server and application logic
- `family_tree.py`: Core classes for Animal and Colony management
- `tree_visualization.py`: Dash application for interactive tree visualization
- `templates/`: HTML templates for the web interface
- `colonies/`: Directory for storing colony data (created automatically)

## Requirements

- Python 3.7+
- Flask
- Dash
- NetworkX
- Matplotlib
- PyQt5
- Other dependencies listed in requirements.txt

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
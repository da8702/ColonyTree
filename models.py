from datetime import date
from typing import Optional, List
import json

class Animal:
    def __init__(self, animal_id: str, sex: str, genotype: str, dob: date,
                 mother: Optional["Animal"] = None, father: Optional["Animal"] = None,
                 notes: Optional[str] = None, cage_id: Optional[str] = None,
                 date_weaned: Optional[date] = None):
        self.animal_id = animal_id
        self.sex = sex
        self.genotype = genotype
        self.dob = dob
        self.mother = mother
        self.father = father
        self.children: List["Animal"] = []
        self.notes = notes
        self.cage_id = cage_id
        self.old_cage_id: Optional[str] = None
        self.date_weaned = date_weaned
        self.deceased = False

        # Automatically link to parents' children lists
        if mother:
            mother.children.append(self)
        if father:
            father.children.append(self)

    def __str__(self):
        return f"{self.animal_id} ({self.sex}) - {self.genotype}"
    
    def to_dict(self):
        """Convert animal to dictionary for JSON serialization"""
        return {
            'animal_id': self.animal_id,
            'sex': self.sex,
            'genotype': self.genotype,
            'dob': self.dob.isoformat(),
            'mother_id': self.mother.animal_id if self.mother else None,
            'father_id': self.father.animal_id if self.father else None,
            'notes': self.notes,
            'cage_id': self.cage_id,
            'date_weaned': self.date_weaned.isoformat() if self.date_weaned else None,
            'old_cage_id': self.old_cage_id,
            'deceased': self.deceased
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create animal from dictionary"""
        date_weaned = None
        if data.get('date_weaned'):
            try:
                date_weaned = date.fromisoformat(data['date_weaned'])
            except (ValueError, TypeError):
                date_weaned = None
                
        animal = cls(
            animal_id=data['animal_id'],
            sex=data['sex'],
            genotype=data['genotype'],
            dob=date.fromisoformat(data['dob']),
            notes=data.get('notes'),
            cage_id=data.get('cage_id'),
            date_weaned=date_weaned
        )
        animal.deceased = data.get('deceased', False)
        # Set old_cage_id if present
        if data.get('old_cage_id'):
            animal.old_cage_id = data['old_cage_id']
        return animal

class Colony:
    def __init__(self, name: str):
        self.name = name
        self.animals: List[Animal] = []
        self.breeder_cages: List[dict] = []

    def add_animal(self, animal: Animal):
        """Add an animal to the colony"""
        if any(a.animal_id == animal.animal_id for a in self.animals):
            raise ValueError(f"Animal with ID {animal.animal_id} already exists")
        self.animals.append(animal)
    
    def get_animal(self, animal_id):
        """Get an animal by its ID"""
        return next((a for a in self.animals if a.animal_id == animal_id), None)
    
    def get_animal_by_id(self, animal_id):
        """Get an animal by its ID"""
        return next((a for a in self.animals if a.animal_id == animal_id), None)
    
    def update_animal_id(self, old_id, new_id):
        """Update an animal's ID and all references to it"""
        animal = self.get_animal_by_id(old_id)
        if not animal:
            return False
            
        # Update the animal's ID
        animal.animal_id = new_id
        
        # Update references in other animals
        for a in self.animals:
            # Update mother references
            if a.mother and isinstance(a.mother, str) and a.mother == old_id:
                a.mother = new_id
            elif a.mother and hasattr(a.mother, 'animal_id') and a.mother.animal_id == old_id:
                # Mother is an Animal object
                a.mother.animal_id = new_id
                
            # Update father references
            if a.father and isinstance(a.father, str) and a.father == old_id:
                a.father = new_id
            elif a.father and hasattr(a.father, 'animal_id') and a.father.animal_id == old_id:
                # Father is an Animal object
                a.father.animal_id = new_id
                
            # Update children references
            if isinstance(a.children, list):
                # Children could be a list of strings (IDs) or Animal objects
                for i, child in enumerate(a.children):
                    if isinstance(child, str) and child == old_id:
                        a.children[i] = new_id
                    elif hasattr(child, 'animal_id') and child.animal_id == old_id:
                        child.animal_id = new_id
                
        return True
    
    def get_founders(self):
        """Get all animals without parents"""
        return [a for a in self.animals if not a.mother and not a.father]
    
    def get_children(self, animal):
        """Get all children of an animal"""
        return [a for a in self.animals if a.mother == animal or a.father == animal]
    
    def get_siblings(self, animal):
        """Get all siblings of an animal"""
        siblings = []
        if animal.mother:
            siblings.extend([a for a in animal.mother.children if a != animal])
        if animal.father:
            siblings.extend([a for a in animal.father.children if a != animal])
        return list(set(siblings))  # Remove duplicates
    
    def get_cousins(self, animal):
        """Get all cousins of an animal"""
        cousins = []
        for parent in [animal.mother, animal.father]:
            if parent:
                for uncle in self.get_siblings(parent):
                    cousins.extend(uncle.children)
        return list(set(cousins))  # Remove duplicates
    
    def get_unique_cage_ids(self):
        """Get all unique cage IDs in the colony"""
        return sorted(list(set(a.cage_id for a in self.animals if a.cage_id)))
    
    def get_males(self):
        """Get all male animals in the colony"""
        # Accept both 'M' and 'Male' values
        return [a for a in self.animals if (isinstance(a.sex, str) and a.sex in ('M', 'Male'))]

    def get_females(self):
        """Get all female animals in the colony"""
        # Accept both 'F' and 'Female' values
        return [a for a in self.animals if (isinstance(a.sex, str) and a.sex in ('F', 'Female'))]

    def get_animal_with_cage(self, animal_id):
        """Get an animal by its ID, including cage information"""
        animal = self.get_animal(animal_id)
        if animal:
            return {
                'animal_id': animal.animal_id,
                'sex': animal.sex,
                'genotype': animal.genotype,
                'dob': animal.dob.isoformat(),
                'mother_id': animal.mother.animal_id if animal.mother else None,
                'father_id': animal.father.animal_id if animal.father else None,
                'notes': animal.notes,
                'cage_id': animal.cage_id
            }
        return None
    
    def to_dict(self):
        """Convert colony to dictionary for JSON serialization"""
        data = {
            'name': self.name,
            'animals': [animal.to_dict() for animal in self.animals],
            'breeder_cages': self.breeder_cages
        }
        return data
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create colony from dictionary"""
        colony = cls(data['name'])
        
        # First pass: create all animals without relationships
        animal_dict = {}
        for animal_data in data['animals']:
            animal = Animal.from_dict(animal_data)
            colony.add_animal(animal)
            animal_dict[animal.animal_id] = animal
        
        # Second pass: establish relationships
        for animal_data in data['animals']:
            animal = animal_dict[animal_data['animal_id']]
            if animal_data['mother_id']:
                mother = animal_dict[animal_data['mother_id']]
                animal.mother = mother
                mother.children.append(animal)
            if animal_data['father_id']:
                father = animal_dict[animal_data['father_id']]
                animal.father = father
                father.children.append(animal)
        colony.breeder_cages = data.get('breeder_cages', [])
        return colony

    def to_json(self):
        """Convert colony to JSON string for serialization"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def load_from_json(cls, json_str):
        """Create colony from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data) 
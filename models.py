from datetime import date
from typing import Optional, List

class Animal:
    def __init__(self, animal_id: str, sex: str, genotype: str, dob: date,
                 mother: Optional["Animal"] = None, father: Optional["Animal"] = None,
                 notes: Optional[str] = None):
        self.animal_id = animal_id
        self.sex = sex
        self.genotype = genotype
        self.dob = dob
        self.mother = mother
        self.father = father
        self.children: List["Animal"] = []
        self.notes = notes

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
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create animal from dictionary"""
        return cls(
            animal_id=data['animal_id'],
            sex=data['sex'],
            genotype=data['genotype'],
            dob=date.fromisoformat(data['dob']),
            notes=data['notes']
        )

class Colony:
    def __init__(self, name: str):
        self.name = name
        self.animals: List[Animal] = []

    def add_animal(self, animal: Animal):
        """Add an animal to the colony"""
        if any(a.animal_id == animal.animal_id for a in self.animals):
            raise ValueError(f"Animal with ID {animal.animal_id} already exists")
        self.animals.append(animal)
    
    def get_animal(self, animal_id):
        """Get an animal by its ID"""
        return next((a for a in self.animals if a.animal_id == animal_id), None)
    
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
    
    def to_dict(self):
        """Convert colony to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'animals': [animal.to_dict() for animal in self.animals]
        }
    
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
        
        return colony 
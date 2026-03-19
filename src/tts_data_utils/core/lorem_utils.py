"""
Utilities for generating lorem ipsum dummy data for DataContainer instances.

This module provides functions to generate realistic dummy data based on
the structure defined in a DataItem class.
"""

import random
from datetime import datetime, timedelta
import string
import uuid

# Lorem ipsum words for generating text
LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
    "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore",
    "magna", "aliqua", "enim", "ad", "minim", "veniam", "quis", "nostrud", "exercitation",
    "ullamco", "laboris", "nisi", "aliquip", "ex", "ea", "commodo", "consequat",
    "duis", "aute", "irure", "reprehenderit", "voluptate", "velit", "esse", "cillum",
    "dolore", "fugiat", "nulla", "pariatur", "excepteur", "sint", "occaecat", "cupidatat",
    "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt", "mollit", "anim",
    "id", "est", "laborum"
]

# Common status values
STATUS_VALUES = ["pending", "in_progress", "completed", "failed", "success", "unknown", "error"]

# Common severity levels
SEVERITY_LEVELS = ["info", "debug", "warning", "error", "critical"]

def generate_lorem_text(min_words=3, max_words=10):
    """Generate lorem ipsum text with a random number of words."""

    # nosec B311: Standard random is fine for placeholder text (not cryptographic)
    num_words = random.randint(min_words, max_words) #nosec
    text = " ".join(random.sample(LOREM_WORDS, k=min(num_words, len(LOREM_WORDS)))) #nosec
    return text.capitalize()

def generate_value_for_type(type_spec):
    """
    Generate a random value that matches the given type specification.
    
    Args:
        type_spec: A type or tuple of types (from DICT_VALID_KEYS)
        
    Returns:
        A random value of the appropriate type
    """
    # If type_spec is not a tuple, make it one for consistent handling
    if not isinstance(type_spec, tuple):
        types = (type_spec,)
    else:
        types = type_spec
    
    # If None is an acceptable type, occasionally return None
    if None in types and random.random() < 0.1: #nosec
        return None
    
    # Filter out None from types for actual value generation
    valid_types = [t for t in types if t is not None]
    
    # If no valid types remain, return None
    if not valid_types:
        return None
    
    # Choose a random type from the valid options
    chosen_type = random.choice(valid_types) #nosec
    
    # Generate a value based on the chosen type
    if chosen_type == str:
        # For strings, generate different formats based on field name patterns
        return generate_lorem_text(2, 8)
    elif chosen_type == int:
        return random.randint(0, 10000) #nosec
    elif chosen_type == float:
        return round(random.uniform(0, 100), 2) #nosec
    elif chosen_type == bool:
        return random.choice([True, False]) #nosec
    elif chosen_type == datetime:
        # Generate a random datetime within the last year
        days_ago = random.randint(0, 365) #nosec
        return datetime.now().replace(microsecond=0) - timedelta(days=days_ago)
    elif chosen_type == dict:
        # Generate a simple dictionary with 1-3 key-value pairs
        num_items = random.randint(1, 3) #nosec
        return {f"key{i}": generate_lorem_text(1, 3) for i in range(num_items)}
    elif chosen_type == list:
        # Generate a list with 1-5 string items
        num_items = random.randint(1, 5) #nosec
        return [generate_lorem_text(1, 2) for _ in range(num_items)]
    else:
        # For any other types, return a string representation
        return str(chosen_type.__name__)

def generate_smart_value(key, type_spec):
    """
    Generate a value for a specific key, using naming conventions to create more realistic data.
    
    Args:
        key: The field name
        type_spec: The type specification
        
    Returns:
        A value appropriate for the field name and type
    """
    # Handle common field name patterns
    key_lower = key.lower()
    
    # Handle None in type_spec
    if isinstance(type_spec, tuple) and None in type_spec and random.random() < 0.1: #nosec
        return None
    
    # ID fields
    if key_lower in ('id', 'channelid', 'eventid', 'sessionid') or key_lower.endswith('id'):
        if isinstance(type_spec, tuple):
            if str in type_spec:
                return f"ID-{random.randint(1000, 9999)}" #nosec
            elif int in type_spec:
                return random.randint(1000, 9999) #nosec
        elif type_spec == int:
            return random.randint(1000, 9999) #nosec
        elif type_spec == str:
            return f"ID-{random.randint(1000, 9999)}" #nosec
    
    # Name fields
    if key_lower == 'name' or key_lower.endswith('name'):
        return generate_lorem_text(1, 3)
    
    # Message fields
    if 'message' in key_lower:
        return generate_lorem_text(5, 15)
    
    # Status fields
    if 'status' in key_lower:
        return random.choice(STATUS_VALUES) #nosec
    
    # Level or severity fields
    if 'level' in key_lower or 'severity' in key_lower:
        return random.choice(SEVERITY_LEVELS) #nosec
    
    # Time fields
    if any(time_word in key_lower for time_word in ['time', 'date', 'scet', 'ert', 'lst', 'rct']):
        if isinstance(type_spec, tuple):
            if datetime in type_spec:
                days_ago = random.randint(0, 365) #nosec
                return datetime.now().replace(microsecond=0) - timedelta(days=days_ago)
            elif str in type_spec:
                # Return an ISO format date string
                days_ago = random.randint(0, 365) #nosec
                dt = datetime.now() - timedelta(days=days_ago)
                return dt.isoformat()
        elif type_spec == datetime:
            days_ago = random.randint(0, 365) #nosec
            return datetime.now().replace(microsecond=0) - timedelta(days=days_ago)
        elif type_spec == str:
            days_ago = random.randint(0, 365) #nosec
            dt = datetime.now() - timedelta(days=days_ago)
            return dt.isoformat()
    
    # Clock fields
    if 'sclk' in key_lower:
        return random.uniform(1000000, 9999999) #nosec
    
    # Boolean fields
    if any(bool_word in key_lower for bool_word in ['is_', 'has_', 'can_', 'should_', 'fromsse', 'realtime']):
        return random.choice([True, False]) #nosec
    
    # Fallback to generic value generation
    return generate_value_for_type(type_spec)

def generate_lorem_data_for_item(data_item_cls, num_records=10):
    """
    Generate lorem ipsum data for a specific DataItem class.
    
    Args:
        data_item_cls: The DataItem class to generate data for
        num_records: Number of records to generate
        
    Returns:
        List of dictionaries with dummy data matching the DataItem structure
    """
    data = []
    
    # If the class has no DICT_VALID_KEYS, generate generic data
    if not hasattr(data_item_cls, 'DICT_VALID_KEYS') or not data_item_cls.DICT_VALID_KEYS:
        for i in range(num_records):
            record = {
                "id": i + 1,
                "title": generate_lorem_text(2, 5),
                "description": generate_lorem_text(10, 20),
                "timestamp": datetime.now() - timedelta(days=random.randint(0, 365)), #nosec
                "value": round(random.uniform(0, 100), 2), #nosec
                "count": random.randint(1, 1000), #nosec
                "status": random.choice(STATUS_VALUES) #nosec
            }
            data.append(record)
        return data
    
    # Generate data based on DICT_VALID_KEYS
    for i in range(num_records):
        record = {}
        for key, type_spec in data_item_cls.DICT_VALID_KEYS:
            record[key] = generate_smart_value(key, type_spec)
        data.append(record)
    
    return data

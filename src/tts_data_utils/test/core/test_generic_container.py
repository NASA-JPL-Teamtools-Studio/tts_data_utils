#Standard Library Imports
import json
import pdb
import pandas as pd
from pathlib import Path

#Installed Library Importsimport pytest
from datetime import datetime
import pytest

#Teamtool Studio Imports
from tts_utilities.logger import create_logger
from tts_utilities.test_utilities import safe_test_paths

#This Library Imports
from tts_data_utils.core.generic import GenericContainer

def test_generic_init_empty():
    """Ensure initializing an empty generic container doesn't crash."""
    container = GenericContainer(raw_data=[])
    assert len(container) == 0
    assert container.name == 'Generic Container'
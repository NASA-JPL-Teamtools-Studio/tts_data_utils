import pdb
from abc import ABC, abstractmethod

from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_item import DataItem

from jpl_time import Time

class PlanningRuleItem(DataItem):
    """
    A specialized record representing a mission constraint or operational rule.

    **The Concept:**
    Planning rules are the "laws" of a spacecraft's schedule. They define what the 
    spacecraft can and cannot do (e.g., "Do not point the instrument at the sun 
    while the cover is open"). 

    A `PlanningRuleItem` captures the metadata of these constraints, allowing 
    automated schedulers or human planners to understand the risk and impact 
    associated with violating a specific mission requirement.

    **Database Integration:**
    This class includes a `DJANGO_KEY_MAP` to handle the translation between 
    database-friendly snake_case fields (used in the Planning Service) and 
    report-friendly Title Case fields used in this library.

    :param Rule ID: Unique identifier for the planning constraint.
    :type Rule ID: str
    :param Functional Category: The subsystem the rule applies to (e.g., 'ADCS', 'Power').
    :type Functional Category: str
    :param Maturity: The current status of the rule (e.g., 'Draft', 'Flight Validated').
    :type Maturity: str
    :param Title: A short, descriptive name for the rule.
    :type Title: str
    :param Description: The full text of the constraint.
    :type Description: str
    :param Violation Impact: Explanation of what happens if this rule is broken.
    :type Violation Impact: str
    :param Criticality: Severity of the rule (e.g., 'High', 'Mission Ending').
    :type Criticality: str
    """

    DICT_VALID_KEYS = [
        ('Rule ID', str),
        ('Functional Category', str),
        ('Maturity', str),
        ('Title', str),
        ('Description', str),
        ('Violation Impact', str),
        ('Criticality', str),
        ]

    TIME_FORMATS = {}

    DJANGO_KEY_MAP = {
        'uuid': 'uuid',
        'rule_id': 'Rule ID',
        'functional_category': 'Functional Category',
        'maturity': 'Maturity',
        'title': 'Title',
        'description': 'Description',
        'impact_of_violation': 'Violation Impact',
        'criticality': 'Criticality',
    }

    def __sub_init(self):
        """Internal initialization hook."""
        return

    def time(self):
        """
        [Disabled] 
        
        Planning rules are static constraints and do not have a single 
        point-in-time association.
        """
        return


class PlanningRuleContainer(DataContainer):
    """
    **The Concept:**
    This container acts as a digital "Rulebook." When generating a mission 
    plan or analyzing a sequence of commands, this container is used to 
    look up the definitions and impacts of the rules being checked.

    **Mission Specifics:**
    While named for OCO-2, the structure follows the standard patterns 
    required for any mission using the Teamtools Studio planning validation 
    workflow.
    """
    NAME = 'Planning Rule'
    DATA_ITEM_CLS = PlanningRuleItem
    DO_NOT_DIFF = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    @property
    def repr_cols(self):
        """
        The list of columns intended for display in rule reports.
        """
        #this is here because it's an abstract method, which may
        #not be useful. Consider removal
        return self._repr_cols
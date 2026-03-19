from jpl_time import Time

from dexter.core.data import DataItem, DataContainer
from dexter.core.dispo import Dispositioner, dispo_method
from dexter.util.utilities import cached_property, filter_on_attr_regex

class TacoItem(DataItem):    
    @property
    def valid(self):
        # Just double-check we have the right object type
        # TODO: Add additional validation checks here.
        # This isn't good enough.
        return isinstance(self.source, dict)

    @property
    def time(self):
        return None
    
    # @cached_property
    # def start_time(self):
    #     return Time(self.source.get_start_lmst())
    
    # @cached_property
    # def end_time(self):
    #     return Time(self.source.get_end_lmst())
    
    # @property
    # def time(self):
    #     return self.start_time
    
    def stamp(self, dispo_value):
        pass
    
    # @property
    # def seq_id(self):
    #     return self.source.seq_id

class TacoContainer(DataContainer):
    NAME = 'taco'
    DATA_ITEM_CLS = TacoItem
    
    # @classmethod
    # def _format_data(cls, raw_data, copy_data, default_dispo):
    #     # Default is just to assume a list of data payloads that can be passed directly to the DataItem class
    #     return [cls.DATA_ITEM_CLS(_, copy_data=copy_data, default_dispo=default_dispo) for _ in raw_data.get_executions()]
    
    # def get_exec_by_seq_id(self, seq_id):
    #     """Gets all executions of a particular Seq ID as a list, allowing regex"""
    #     return filter_on_attr_regex(self.data, seq_id=seq_id)
    
    # def get_exec_by_seq_id_exact(self, seq_id):
    #     """Gets all executions of a particular SeqID as a list, exact match only (e.x. 'aut_00000' must match, version ignored)"""
    #     return [_ for _ in self.data if _.seq_id == seq_id]

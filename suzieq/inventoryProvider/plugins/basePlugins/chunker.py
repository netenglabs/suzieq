from abc import abstractmethod

class Chunker:
    @abstractmethod
    def chunk(self, glob_inv, n_pollers, **addl_params):
        ''' 
        Split the global inventory in <n_chunks> chunks 
        
        addl_parameters: this field could be used to specify additional parameters
                         to say how to split the global inventory
        '''
        pass

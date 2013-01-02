import unittest
import os
import sys
import anydbm

import Runtime
import Resource



class Resource_Storage(unittest.TestCase):

    """
    Test Storage interface.
    """
       

class Resource_Descriptor(unittest.TestCase):

    def test_(self):
        pass # Descriptor(storage).load_from_storage(path)/drop/update/commit/data


class Resource_backend(unittest.TestCase):

    """
    Test wether get/open/close backend works. 
    """

    def test_1_init(self):
        self.assertTrue(Resource.backend == None)
        Runtime.DATA_DIR = '/tmp/htache-unittest-data'
        if not os.path.exists(Runtime.DATA_DIR):
            os.mkdir(Runtime.DATA_DIR)
        Resource.get_backend()
        self.assertTrue(Resource.backend != None)
        Resource.close_backend()

    def test_2_ro(self):
        self.assertTrue(Resource.backend == None)
        Runtime.DATA_DIR = '/tmp/htache-unittest-data'
        Resource.get_backend(True)
        Resource.close_backend()


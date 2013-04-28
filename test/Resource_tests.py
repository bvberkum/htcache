import unittest
import os
import sys
import anydbm

import Runtime
import Resource
from Command import CLIParams


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
        Runtime.DATA_DIR = '/tmp/htache-unittest-data'
        if not os.path.exists(Runtime.DATA_DIR):
            os.mkdir(Runtime.DATA_DIR)
        CLIParams.parse(['--data-dir', Runtime.DATA_DIR])
        be = Resource.get_backend()
        print Resource
        #Resource.close_backend()

    def test_2_ro(self):
        Runtime.DATA_DIR = '/tmp/htache-unittest-data'
        CLIParams.parse(['--data-dir', Runtime.DATA_DIR])
        print Resource.get_backend(read_only=True)
        print Resource
        #Resource.close_backend()


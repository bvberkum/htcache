import unittest
import os
import sys
import anydbm

import Runtime
import Resource



class Resource_Storage_Factory(unittest.TestCase):

    """
    test if factory produces anydbm like object
    """

    def test_(self):
        path = '/tmp/htcache-Resource_Storage_Factory-test.db'

        storage = Resource.index_factory(None, path, 'w')
        key = '123'
        storage[key] = 'test'
        storage.close()

        storage = Resource.index_factory(None, path, 'r')
        def _set(k, v): 
            storage[k] = v
        self.assertRaises(anydbm.error, _set, key, 'newvalue')
        storage.close()

        self.assertTrue(os.path.isfile(path))
        os.unlink(path)


class Resource_Storage(unittest.TestCase):

    """
    Test Storage interface.
    """

    def test_1_factories(self):
        """
        Test if factories exists.
        """
        for name in ('ResourceStorage', 'DescriptorStorage', \
                'ResourceMap', 'CacheMap'):
            factory = getattr(Resource.Storage, "%sFactory" % name)
            self.assertTrue(callable(factory))
       

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
        Resource.open_backend()
        self.assertTrue(isinstance(Resource.backend, Resource.Storage))
        Resource.close_backend()

    def test_2_ro(self):
        self.assertTrue(Resource.backend == None)
        Runtime.DATA_DIR = '/tmp/htache-unittest-data'
        Resource.open_backend(True)
        self.assertTrue(isinstance(Resource.backend, Resource.Storage))
        Resource.close_backend()


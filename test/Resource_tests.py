import unittest
import os
import sys
import anydbm

import Resource



class Resource_Storage_Factory(unittest.TestCase):

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

	def test_1_factories(self):
		for name in ('ResourceStorage', 'DescriptorStorage', \
				'ResourceMap', 'CacheMap'):
			factory = getattr(Resource.Storage, "%sFactory" % name)
			self.assertTrue(callable(factory))
	   

class Resource_Descriptor(unittest.TestCase):

	def test_(self):
		pass # Descriptor(storage).load_from_storage(path)/drop/update/commit/data


class Resource_backend(unittest.TestCase):

	def test_(self):
		self.assertTrue(Resource.backend == None)
		Resource.open_backend(True)
		self.assertTrue(isinstance(Resource.backend, Resource.Storage))


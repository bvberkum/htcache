import os

import unittest

import Params
import Runtime
import Rules
from Request import HtRequest
from Protocol import ProxyProtocol
from Response import ProxyResponse


class Response_Tests(unittest.TestCase):

	def test_1_echo_proxy_response(self):
		req = HtRequest()
		req._HtRequest__verb = 'get'
		req._HtRequest__body = ''
		req._HtRequest__reqpath = '/echo'
		req._HtRequest__prototag = 'HTTP/1.0'
		req._HtRequest__headers = {}
		req.Protocol = ProxyProtocol
		proto = ProxyProtocol(req)
		resp = ProxyResponse( proto, req )
		self.assert_(resp._DirectResponse__sendbuf)

	def test_2_script_proxy_response(self):
		req = HtRequest()
		req._HtRequest__verb = 'get'
		req._HtRequest__body = ''
		req._HtRequest__reqpath = '/dhtml.css'
		req._HtRequest__prototag = 'HTTP/1.0'
		req._HtRequest__headers = {}
		req.Protocol = ProxyProtocol
		proto = ProxyProtocol(req)
		resp = ProxyResponse( proto, req )
		self.assert_(resp._DirectResponse__sendbuf)


if __name__ == '__main__':
    unittest.main()


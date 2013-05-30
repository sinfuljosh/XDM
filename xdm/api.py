# Author: Dennis Lutter <lad1337@gmail.com>
# URL: https://github.com/lad1337/XDM
#
# This file is part of XDM: eXtentable Download Manager.
#
#XDM: eXtentable Download Manager. Plugin based media collection manager.
#Copyright (C) 2013  Dennis Lutter
#
#XDM is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#XDM is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see http://www.gnu.org/licenses/.

import sys
import os
import xdm
from xdm.logger import *
from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import threading
from xdm import actionManager, common, tasks
import json

from functools import partial, update_wrapper
from jsonrpclib.jsonrpc import ProtocolError, Fault
import types

DONTNEEDAPIKEY = ('ping', 'version')


class ApiDispatcher(object):

    def __init__(self):
        self._exposed = {}

    def exposeThis(self, fn, name):
        self._exposed[name] = fn

    def _listMethods(self):
        return self._exposed.keys()

    def _dispatch(self, method, params):
        #TODO: log api calls
        checkApiKey = True
        if method in DONTNEEDAPIKEY:
            checkApiKey = False
        if method in self._exposed:
            func = self._exposed[method]
            if checkApiKey:
                if  params and type(params) is types.ListType:
                    if params[0] != common.SYSTEM.c.api_key:
                        return Fault(-31121, "Missing or wrong API key")
                    else:# correct api key as list
                        del params[0]
                elif 'apikey' not in params:
                    return Fault(-31121, "Missing API key")
                elif params['apikey'] != common.APIKEY:
                    return Fault(-31123, "API key denied access")
                else:# correct api key as keyword
                    del params['apikey']
            try:
                if type(params) is types.ListType:
                    response = func(*params)
                else:
                    response = func(**params)
                return response
            except TypeError:
                return Fault(-32602, 'Invalid parameters.')
        else:
            return Fault(-32601, 'Method %s not supported.' % method)

apiDispatcher = ApiDispatcher()


class expose(object):
    """Expose the function by adding it to the apiDispatcher"""
    def __init__(self, target):
        self.target = target
        self.__name__ = self.target.__name__
        if target.__module__.startswith('xdm.api'):
            exposedFunctionName = self.__name__
        else:
            namespace = target.__module__.split('.')[-1].lower()
            exposedFunctionName = "%s.%s" % (namespace, self.__name__)

        apiDispatcher.exposeThis(self, exposedFunctionName)

    #http://stackoverflow.com/questions/8856164/class-decorator-decorating-method-in-python
    def __get__(self, obj, type=None):
        self.obj = obj
        return self

    def __call__(self, *args, **kwargs):
        try:
            obj = self.obj
        except AttributeError: # if this is not an instance method self.obj is not defined
            return self.target(*args, **kwargs)
        else:
            return self.target(obj, *args, **kwargs)


class JSONRPCapi(threading.Thread):

    def __init__(self, port):
        self.server = SimpleJSONRPCServer(('localhost', port), logRequests=False)
        self.server.register_instance(apiDispatcher)
        self.server.register_introspection_functions()

        threading.Thread.__init__(self)

    def run(self):
        self.server.serve_forever()

    def register_function(self, *args, **kwargs):
        self.server.register_function(*args, **kwargs)


@expose
def ping():
    """Returns 'pong' nice way to test the connections"""
    return 'pong'


@expose
def version():
    """Returns the XDM version tuple as a list e.g. [0, 4, 13, 0]"""
    return common.getVersionTuple()


@expose
def reboot():
    """just return True and starts a thread to reboot XDM"""
    common.SM.reset()
    t = tasks.TaskThread(actionManager.executeAction, 'reboot', 'JSONRPCapi')
    t.start()
    return True


@expose
def shutdown():
    """just return True and starts a thread to shutdown XDM"""
    common.SM.reset()
    t = tasks.TaskThread(actionManager.executeAction, 'shutdown', 'JSONRPCapi')
    t.start()
    return True


@expose
def getActiveMediaTypes():
    return [mtm.identifier for mtm in common.PM.MTM]
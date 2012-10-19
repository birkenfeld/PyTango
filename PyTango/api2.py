################################################################################
##
## This file is part of PyTango, a python binding for Tango
## 
## http://www.tango-controls.org/static/PyTango/latest/doc/html/index.html
##
## Copyright 2011 CELLS / ALBA Synchrotron, Bellaterra, Spain
## 
## PyTango is free software: you can redistribute it and/or modify
## it under the terms of the GNU Lesser General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
## 
## PyTango is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Lesser General Public License for more details.
## 
## You should have received a copy of the GNU Lesser General Public License
## along with PyTango.  If not, see <http://www.gnu.org/licenses/>.
##
################################################################################

"""This module provides a high level device server API. It implements
:ref:`TEP1 <pytango-TEP1>`. It exposes an easier API for developing a tango
device server.

Here is the summary of features which this module exposes and are not available
on the low level :mod:`PyTango` server API:

#. Automatic inheritance from the latest :class:`~PyTango.DeviceImpl`
#. default implementation of :meth:`Device.__init__`
   calls :meth:`Device.init_device`. Around 90% of the
   different device classes which inherit from low level
   :class:`~PyTango.DeviceImpl` only implement `__init__` to call their
   `init_device`
#. has a default implementation of :meth:`Device.init_device`
   which calls :meth:`Device.get_device_properties`. Again,
   90% of existing device classes do that
#. Automatically creates a hidden :class:`~PyTango.DeviceClass` class 
#. recognizes :func:`attribute` members and automatically 
   registers them as tango attributes in the hidden
   :class:`~PyTango.DeviceClass`
#. recognizes :class:`command` decorated functions and
   automatically registers them as tango commands in the hidden
   :class:`~PyTango.DeviceClass`
#. recognizes :func:`device_property` members and
   automatically registers them as tango device properties in the hidden
   :class:`~PyTango.DeviceClass`
#. recognizes :func:`class_property` members and
   automatically registers them as tango class properties in the hidden
   :class:`~PyTango.DeviceClass`
#. read and write attribute methods don't need :class:`~PyTango.Attribute`
   parameter. Access to :class:`~PyTango.Attribute` object is with simple::
   
       self.<attr name>
       
#. read attribute methods can set attribute return value with::
       
       self.<attr name> = <value>
       
   instead of::
   
       attr.set_value(<value>)

:class:`Device` works very well in conjuction with:

#. :meth:`attribute`
#. :class:`command`
#. :meth:`device_property`
#. :meth:`class_property`
#. :meth:`~PyTango.server_run`

Here is an example of a PowerSupply device with:

#. a read-only double scalar `voltage` attribute
#. a read/write double scalar `current` attribute
#. a `ramp` command
#. a `host` device property

.. code-block:: python
    :linenos:

    from time import time
        
    from PyTango import AttrQuality, DebugIt, server_run
    from PyTango.api2 import Device, DeviceMeta
    from PyTango.api2 import attribute, command, device_property

    class PowerSupply(Device):
        __metaclass__ = DeviceMeta
        
        voltage = attribute()        

        current = attribute(label="Current", unit="A",
                            fread="read_current",
                            fwrite="write_current")
        
        host = device_property()
        
        def read_voltage(self):
            self.voltage = 10.0
            
        def read_current(self):
            self.current = 2.5, time(), AttrQuality.ON
        
        @DebugIt()
        def write_current(self):
            new_current = self.current.get_write_value()
        
        @command()
        def ramp(self):
            self.info_stream("Ramping on " + self.host + "...")

    def main():
        classes = PowerSupply,
        server_run(classes)
    
    if __name__ == "__main__":
        main()

And here is the equivalent code using the low-level API:

.. code-block:: python
    :linenos:

    import sys
    import time

    import PyTango

    class PowerSupply(PyTango.Device_4Impl):

        def __init__(self, devclass, name):
            PyTango.Device_4Impl.__init__(self, devclass, name)
            self.init_device()
        
        def init_device(self):
            self.get_device_properties()
        
        def read_voltage(self, attr):
            attr.set_value(10.0)
            
        def read_current(self):
            attr.set_value_date_quality(2.5, time.time(), PyTango.AttrQuality.ON)
        
        @PyTango.DebugIt()
        def write_current(self, attr):
            new_current = attr.get_write_value()
        
        def ramp(self):
            self.info_stream("Ramping on " + self.host + "...")


    class PowerSupplyClass(PyTango.DeviceClass):
        
        class_property_list = {}

        device_property_list = {
            'host':
                [PyTango.DevString, "host of power supply", "localhost"],
        }

        cmd_list = {
            'ramp':
                [ [PyTango.DevVoid, "nothing"],
                  [PyTango.DevVoid, "nothing"] ],
        }

        attr_list = {
            'voltage':
                [[PyTango.DevDouble,
                PyTango.SCALAR,
                PyTango.READ]],
            'current':
                [[PyTango.DevDouble,
                PyTango.SCALAR,
                PyTango.READ_WRITE], 
                { 'label' : 'Current', 'unit' : 'A' }],
        }
        

    def main():
        try:
            py = PyTango.Util(sys.argv)
            py.add_class(PowerSupplyClass,PowerSupply,'PowerSupply')

            U = PyTango.Util.instance()
            U.server_init()
            U.server_run()

        except PyTango.DevFailed,e:
            print '-------> Received a DevFailed exception:',e
        except Exception,e:
            print '-------> An unforeseen exception occured....',e

    if __name__ == "__main__":
        main()
        
        
*Pretty cool, uh?*
"""

from __future__ import with_statement
from __future__ import print_function

__all__ = ["DeviceMeta", "Device", "LatestDeviceImpl", "attribute", "command",
           "device_property", "class_property"]

import inspect
import functools
import __builtin__

from ._PyTango import DeviceImpl, Attribute, WAttribute, CmdArgType, \
    AttrDataFormat, AttrWriteType, DispLevel, constants
from .attr_data import AttrData
from .device_class import DeviceClass
from .utils import get_tango_device_classes, is_non_str_seq, is_pure_str
from .log4tango import DebugIt

API_VERSION = 2

LatestDeviceImpl = get_tango_device_classes()[-1]

def __build_to_tango_type():
    ret = \
    {
        int         : CmdArgType.DevLong,
        str         : CmdArgType.DevString,
        bool        : CmdArgType.DevBoolean,
        bytearray   : CmdArgType.DevEncoded,
        float       : CmdArgType.DevDouble,
        chr         : CmdArgType.DevUChar,
        None        : CmdArgType.DevVoid,

        'int'       : CmdArgType.DevLong,
        'int16'     : CmdArgType.DevShort,
        'int32'     : CmdArgType.DevLong,
        'int64'     : CmdArgType.DevLong64,
        'uint'      : CmdArgType.DevULong,
        'uint16'    : CmdArgType.DevUShort,
        'uint32'    : CmdArgType.DevULong,
        'uint64'    : CmdArgType.DevULong64,
        'str'       : CmdArgType.DevString,
        'string'    : CmdArgType.DevString,
        'text'      : CmdArgType.DevString,
        'bool'      : CmdArgType.DevBoolean,
        'boolean'   : CmdArgType.DevBoolean,
        'bytes'     : CmdArgType.DevEncoded,
        'bytearray' : CmdArgType.DevEncoded,
        'float'     : CmdArgType.DevDouble,
        'float32'   : CmdArgType.DevFloat,
        'float64'   : CmdArgType.DevDouble,
        'double'    : CmdArgType.DevDouble,
        'byte'      : CmdArgType.DevUChar,
        'chr'       : CmdArgType.DevUChar,
        'char'      : CmdArgType.DevUChar,
        'None'      : CmdArgType.DevVoid,
    }

    for key in dir(CmdArgType):
        if key.startswith("Dev"):
            value = getattr(CmdArgType, key)
            ret[key] = ret[value] = value
            
    if constants.NUMPY_SUPPORT:
        import numpy
        FROM_TANGO_TO_NUMPY_TYPE = { \
                   CmdArgType.DevBoolean : numpy.bool8,
                     CmdArgType.DevUChar : numpy.ubyte,
                     CmdArgType.DevShort : numpy.short,
                    CmdArgType.DevUShort : numpy.ushort,
                      CmdArgType.DevLong : numpy.int32,
                     CmdArgType.DevULong : numpy.uint32,
                    CmdArgType.DevLong64 : numpy.int64,
                   CmdArgType.DevULong64 : numpy.uint64,
                    CmdArgType.DevString : numpy.str,
                    CmdArgType.DevDouble : numpy.float64,
                     CmdArgType.DevFloat : numpy.float32,
        }

        for key,value in FROM_TANGO_TO_NUMPY_TYPE.items():
            ret[value] = key
    
    head = "{0:40}  {0:40}\n".format(40*"=")
    doc = "{0} {1:38}    {2:38} \n{0}".format(head,'type','tango type')
    keys = sorted(ret)
    for key in keys:
        value = ret[key]
        if type(key) == type:
            key_name = key.__name__
            if key_name in __builtin__.__dict__:
                key = ":py:obj:`{0}`".format(key_name)
            elif key.__module__ == 'numpy':
                key = ":py:obj:`numpy.{0}`".format(key_name)
            else:
                key = "``{0}``".format(key_name)
        elif is_pure_str(key):
            key = "``'{0}'``".format(key) 
        else:
            key = "``{0}``".format(key)
        value = "``{0}``".format(value) 
        doc += " {0:38}    {1:38} \n".format(key, str(value))
    doc += head
    return ret, doc
    
TO_TANGO_TYPE, __type_doc = __build_to_tango_type()



def get_tango_type(dtype):
    return TO_TANGO_TYPE[dtype]

get_tango_type.__doc__ = __type_doc

def check_tango_device_klass_attribute_method(tango_device_klass, method_name):
    """Checks if method given by it's name for the given DeviceImpl class has
    the correct signature. If a read/write method doesn't have a parameter
    (the traditional Attribute), then the method is wrapped into another method
    which has correct parameter definition to make it work.
    
    :param tango_device_klass: a DeviceImpl class
    :type tango_device_klass: class
    :param method_name: method to be cheched
    :type attr_data: str"""
    f_obj = real_f_obj = getattr(tango_device_klass, method_name)

    # discover the real method because it may be hidden by a tango decorator
    # like PyTango.DebugIt. Unfortunately we cannot detect other decorators yet
    while hasattr(real_f_obj, "_wrapped"):
        real_f_obj = real_f_obj._wrapped
    argspec = inspect.getargspec(real_f_obj)
    if argspec.varargs and len(argspec.varargs):
        return
    nb = len(argspec.args) - 1
    if argspec.defaults:
        nb -= len(argspec.defaults)
    if nb > 0:
        return
    @functools.wraps(f_obj)
    def f_attr(self, attr):
        return f_obj(self)
    setattr(tango_device_klass, method_name, f_attr)

def check_tango_device_klass_attribute_methods(tango_device_klass, attr_data):
    """Checks if the read and write methods have the correct signature. If a 
    read/write method doesn't have a parameter (the traditional Attribute),
    then the method is wrapped into another method to make this work
    
    :param tango_device_klass: a DeviceImpl class
    :type tango_device_klass: class
    :param attr_data: the attribute data information
    :type attr_data: AttrData"""
    if attr_data.attr_write in (AttrWriteType.READ, AttrWriteType.READ_WRITE):
        check_tango_device_klass_attribute_method(tango_device_klass, attr_data.read_method_name)
    if attr_data.attr_write in (AttrWriteType.WRITE, AttrWriteType.READ_WRITE):
        check_tango_device_klass_attribute_method(tango_device_klass, attr_data.write_method_name)
        
def create_tango_deviceclass_klass(tango_device_klass, attrs=None):
    klass_name = tango_device_klass.__name__
    if not issubclass(tango_device_klass, (Device)):
        raise Exception("{0} device must inherit from PyTango.api2.Device".format(klass_name))
    
    if attrs is None:
        attrs = tango_device_klass.__dict__
        
    attr_list = {}
    for attr_name, attr_obj in attrs.items():
        if isinstance(attr_obj, AttrData2):
            attr_obj._set_name(attr_name)
            attr_list[attr_name] = attr_obj
            check_tango_device_klass_attribute_methods(tango_device_klass, attr_obj)
            
    class_property_list = {}
    device_property_list = {}
    cmd_list = {}
    devclass_name = klass_name + "Class"
    devclass_attrs = dict(class_property_list=class_property_list,
                          device_property_list=device_property_list,
                          cmd_list=cmd_list, attr_list=attr_list)
    return type(devclass_name, (DeviceClass,), devclass_attrs)

def init_tango_device_klass(tango_device_klass, attrs=None, tango_class_name=None):
    klass_name = tango_device_klass.__name__
    tango_deviceclass_klass = create_tango_deviceclass_klass(tango_device_klass,
                                                             attrs=attrs)
    if tango_class_name is None:
        tango_klass_name = klass_name
    tango_device_klass._DeviceClass = tango_deviceclass_klass
    tango_device_klass._DeviceClassName = tango_klass_name
    tango_device_klass._api = API_VERSION
    return tango_device_klass

def create_tango_device_klass(name, bases, attrs):
    klass_name = name

    LatestDeviceImplMeta = type(LatestDeviceImpl)
    klass = LatestDeviceImplMeta(klass_name, bases, attrs)
    init_tango_device_klass(klass, attrs)
    return klass
    
def DeviceMeta(name, bases, attrs):
    """The :py:data:`metaclass` callable for :class:`Device`. Every subclass of
    :class:`Device` must have associated this metaclass to itself in order to
    work properly (boost-python internal limitation).
    
    Example (python 2.x)::
    
        from PyTango.api2 import Device, DeviceMeta

        class PowerSupply(Device):
            __metaclass__ = DeviceMeta

    Example (python 3.x)::
    
        from PyTango.api2 import Device, DeviceMeta

        class PowerSupply(Device, metaclass=DeviceMeta):
            pass
    """
    return create_tango_device_klass(name, bases, attrs)


class Device(LatestDeviceImpl):
    """High level DeviceImpl API.
    
    .. seealso::
        
        Module :py:mod:`PyTango.api2`
            Full API2 documentation"""
    
    def __init__(self, cl, name):
        LatestDeviceImpl.__init__(self, cl, name)
        self.init_device()

    def init_device(self):
        """Tango init_device method. Default implementation calls
        :meth:`get_device_properties`"""
        self.get_device_properties()
    
    def always_executed_hook(self):
        """Tango always_executed_hook. Default implementation does nothing"""
        pass


class AttrData2(AttrData):
    """High level AttrData. To be used """
    
    def get_attribute(self, obj):
        return obj.get_device_attr().get_attr_by_name(self.attr_name)
        
    def __get__(self, obj, objtype):
        return self.get_attribute(obj)

    def __set__(self, obj, value):
        is_tuple = isinstance(value, tuple)
        attr = self.get_attribute(obj)
        dtype, fmt = attr.get_data_type(), attr.get_data_format()
        if dtype == CmdArgType.DevEncoded:
            if is_tuple and len(value) == 4:
                attr.set_value_date_quality(*value)
            elif is_tuple and len(value) == 3 and is_non_str_seq(value[0]):
                attr.set_value_date_quality(value[0][0], value[0][1], *value[1:])
            else:
                attr.set_value(*value)
        else:
            if is_tuple:
                if len(value) == 3:
                    if fmt == AttrDataFormat.SCALAR:
                        attr.set_value_date_quality(*value)
                    elif fmt == AttrDataFormat.SPECTRUM:
                        if is_seq(value[0]):
                            attr.set_value_date_quality(*value)
                        else:
                            attr.set_value(value)
                    else:
                        if is_seq(value[0]) and is_seq(value[0][0]):
                            attr.set_value_date_quality(*value)
                        else:
                            attr.set_value(value)
                else:
                    attr.set_value(value)
            else:
                attr.set_value(value)
    
    def __delete__(self, obj):
        obj.remove_attribute(self.attr_name)
    
def attribute(**kwargs):
    if 'dtype' in kwargs:
        kwargs['dtype'] = get_tango_type(kwargs['dtype'])
    return AttrData2.from_dict(kwargs)


attribute.__doc__ = """\
declares a new tango attribute in a :class:`Device`. To be used like the python
native :obj:`property` function. To declare a scalar, PyTango.DevDouble, read-only
attribute called *voltage* in a *PowerSupply* :class:`Device` do::

    class PowerSupply(Device):
        
        voltage = attribute()
        
        def read_voltage(self):
            self.voltage = 1.0

It receives multiple keyword arguments.

    :param name: alternative attribute name [default: class member name]
    :type name: :obj:`str`
    :param dtype: data type (see :ref:`Data type equivalence <pytango-api2-datatypes>`)
                  [default: :obj:`~PyTango.CmdArgType`\ ``.DevDouble``]
    :type dtype: :obj:`object`
    :param dformat: data format [default: :obj:`~PyTango.AttrDataFormat`\ ``.SCALAR``]
    :type dformat: :obj:`~PyTango.AttrDataFormat`
    :param max_dim_x: maximum size for x dimension (ignored for 
                      :obj:`~PyTango.AttrDataFormat`\ ``.SCALAR`` format) [default: 1]
    :type max_dim_x: :obj:`int`
    :param max_dim_y: maximum size for y dimension (ignored for
                      :obj:`~PyTango.AttrDataFormat`\ ``.SCALAR`` and
                      :obj:`~PyTango.AttrDataFormat`\ ``.SPECTRUM`` formats) [default: 0]
    :type max_dim_y: :obj:`int`
    :param display_level: display level [default: :obj:`~PyTango.DisLevel`\ ``.OPERATOR``]
    :type display_level: :obj:`~PyTango.DispLevel`
    :param polling_period: polling period [default: -1, meaning no polling] 
    :type polling_period: :obj:`int`
    :param memorized: attribute should or not be memorized [default: False]
    :type memorized: :obj:`bool`
    :param hw_memorized: attribute write method should be called at startup when
                         restoring memorize value (dangerous!) [default: False]
    :type hw_memorized: :obj:`bool`
    :param access: read/write access. [default: if no fread and no fwrite methods
                   are given it is :obj:`~PyTango.AttrWriteType`\ ``.READ``. If
                   only fread is given then :obj:`~PyTango.AttrWriteType`\ ``.READ``.
                   if only fwrite is given then :obj:`~PyTango.AttrWriteType`\ ``.WRITE``.
                   if both fread and fwrite are given then :obj:`~PyTango.AttrWriteType`\ ``.READ_WRITE``
    :type access: :obj:`~PyTango.AttrWriteType`
    :param fread: read method name or method object [default: 'read_<attr_name>']
    :type fread: :obj:`str` or :obj:`callable`
    :param fwrite: write method name or method object [default: 'write_<attr_name>']
    :type fwrite: :obj:`str` or :obj:`callable`
    :param is_allowed: is allowed method name or method object [default: 'is_<attr_name>_allowed']
    :type is_allowed: :obj:`str` or :obj:`callable`
    :param label: attribute label
    :type label: obj:`str`
    
.. _pytango-api2-datatypes:

.. rubric:: Data type equivalence 

""" + __type_doc
    
class command:
    """TODO"""
    pass
    
def device_property():
    """TODO"""
    pass

def class_property():
    """TODO"""
    pass


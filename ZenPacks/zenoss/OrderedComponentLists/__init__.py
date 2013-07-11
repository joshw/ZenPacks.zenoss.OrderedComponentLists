import logging
log = logging.getLogger('zen.ZenPacks.zenoss.OrderedComponentLists')

import os
import Globals

from Products.ZenModel.Device import Device
from Products.ZenModel.ZenPack import ZenPack as ZenPackBase
from Products.ZenRelations.RelSchema import ToManyCont, ToOne
from Products.ZenRelations.zPropertyCategory import setzPropertyCategory
from Products.CMFCore.DirectoryView import registerDirectory
from Products.Zuul.interfaces import ICatalogTool
from Products.ZenUtils.Utils import unused, monkeypatch, getSubObjects
from Products.ZenRelations.ToManyContRelationship import ToManyContRelationship
from Products.ZenModel.DeviceComponent import DeviceComponent

unused(Globals)

skinsDir = os.path.join(os.path.dirname(__file__), 'skins')
if os.path.isdir(skinsDir):
    registerDirectory(skinsDir, globals())

ZENPACK_NAME = 'ZenPacks.zenoss.OrderedComponentLists'


# Define new device relations.
NEW_DEVICE_RELATIONS = (
    )

NEW_COMPONENT_TYPES = (
    )

# Add new relationships to Device if they don't already exist.
for relname, modname in NEW_DEVICE_RELATIONS:
    if relname not in (x[0] for x in Device._relations):
        Device._relations += (
            (relname, ToManyCont(ToOne,
            '.'.join((ZENPACK_NAME, modname)), '%s_host' % modname )),
            )

# Useful to avoid making literal string references to module and class names
# throughout the rest of the ZenPack.
MODULE_NAME={}
CLASS_NAME={}
ZP_NAME='ZenPacks.zenoss.OrderedComponentLists'

_PACK_Z_PROPS=[
               ]


_plugins = (
    )

class ZenPack(ZenPackBase):

    packZProperties = _PACK_Z_PROPS

    def install(self,app):
        super(ZenPack, self).install(app)
        log.info('Adding ZenPacks.zenoss.OrderedComponentLists relationships to existing devices')

        self._buildDeviceRelations()
        self.symlink_plugins()

    def symlink_plugins(self):
        libexec = os.path.join(os.environ.get('ZENHOME'), 'libexec')
        if not os.path.isdir(libexec):
            # Stack installs might not have a $ZENHOME/libexec directory.
            os.mkdir(libexec)

        for plugin in _plugins:
            LOG.info('Linking %s plugin into $ZENHOME/libexec/', plugin)
            plugin_path = zenPath('libexec', plugin)
            os.system('ln -sf "%s" "%s"' % (self.path(plugin), plugin_path))
            os.system('chmod 0755 %s' % plugin_path)

    def remove_plugin_symlinks(self):
        for plugin in _plugins:
            LOG.info('Removing %s link from $ZENHOME/libexec/', plugin)
            os.system('rm -f "%s"' % zenPath('libexec', plugin))

    def remove(self, app, leaveObjects=False):
        if not leaveObjects:
            self.remove_plugin_symlinks()

            log.info('Removing ZenPacks.zenoss.OrderedComponentLists components')
            cat = ICatalogTool(app.zport.dmd)

            # Search the catalog for components of this zenpacks type.
            if NEW_COMPONENT_TYPES:
                for brain in cat.search(types=NEW_COMPONENT_TYPES):
                    component = brain.getObject()
                    component.getPrimaryParent()._delObject(component.id)

            # Remove our Device relations additions.
            Device._relations = tuple(
                [x for x in Device._relations \
                    if x[0] not in NEW_DEVICE_RELATIONS])

            log.info('Removing ZenPacks.zenoss.OrderedComponentLists relationships from existing devices')
            self._buildDeviceRelations()

        super(ZenPack, self).remove(app, leaveObjects=leaveObjects)

    def _buildDeviceRelations(self):
        for d in self.dmd.Devices.getSubDevicesGen():
            d.buildRelations()


@monkeypatch('Products.Zuul.facades.devicefacade.DeviceFacade')
def getComponentTree(self, *args, **kwargs):
    """Return a list of dictionaries used to build a device's component tree.

    This method is monkeypatched here to correct the ordering of components.

    """
    # original is injected into locals by monkeypatch.
    result = original(self, *args, **kwargs)
    
    uid = args[0]
    device = self._getObject(uid)
    
    result_bytype = {}
    for r in result:
        result_bytype[r['type']] = r        

    def descend(obj):       
        return (isinstance(obj, ToManyContRelationship) or
                isinstance(obj, DeviceComponent))

    def filter(obj):
        return isinstance(obj, DeviceComponent)

    # depth-first traversal of the components.
    ordered_meta_types = []
    for o in getSubObjects(device, filter=filter, descend=descend):
        if o.meta_type not in ordered_meta_types:
            ordered_meta_types.append(o.meta_type)

    newresult = []
    for meta_type in ordered_meta_types:
        if meta_type in result_bytype:
            newresult.append(result_bytype[meta_type])
            del result_bytype[meta_type]

    # if, for whatever reason, there's something in the original results that we
    # didn't reach through the depth-first traversal, append it alphabetically.
    newresult.extend([result_bytype[x] for x in sorted(result_bytype.keys())])

    return newresult

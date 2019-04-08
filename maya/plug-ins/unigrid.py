import sys
import maya.api.OpenMaya as om
import pymel.core as pm
import maya.cmds as cmds

from UniGrid import ResetSession
import UniGrid
import UniGrid.UnigridToolWindow as UnigridToolWindow



def maya_useNewAPI():
    """
    The presence of this function tells Maya that the plugin produces, and
    expects to be passed, objects created using the Maya Python API 2.0.
    """
    pass

# command
class UnigridTools(om.MPxCommand):
    kPluginCmdName = "showUnigridTools"

    def __init__(self):
        om.MPxCommand.__init__(self)
        self.unigrid_tool_window = None

    @staticmethod
    def cmdCreator():
        return UnigridTools()

    def doIt(self, args):
        unigrid_tool_window = UnigridToolWindow.UnigridToolWindow.instance()
        unigrid_tool_window.show_GUI()

# Initialize the plug-in
def initializePlugin(plugin):
    ResetSession.resetSession()
    pluginFn = om.MFnPlugin(plugin)
    try:
        pluginFn.registerCommand(
            UnigridTools.kPluginCmdName, UnigridTools.cmdCreator
        )
    except:
        sys.stderr.write(
            "Failed to register command: %s\n" % UnigridTools.kPluginCmdName
        )
        raise

    create_menu()

# Uninitialize the plug-in
def uninitializePlugin(plugin):
    pluginFn = om.MFnPlugin(plugin)
    try:
        pluginFn.deregisterCommand(UnigridTools.kPluginCmdName)
    except:
        sys.stderr.write(
            "Failed to unregister command: %s\n" % UnigridTools.kPluginCmdName
        )
        raise

    destroy_menu()
    UnigridToolWindow.UnigridToolWindow.instance().stop()

def create_menu():
    destroy_menu()
    cmds.setParent("MayaWindow")
    unigrid_menu = cmds.menu("unigrid_menu", label="Uni-grid", tearOff=True)
    cmds.menuItem(label="Show Uni-grid tools", command="cmds.showUnigridTools()")
    cmds.setParent("..")

def destroy_menu():
    if cmds.control("unigrid_menu", exists=True):
        cmds.deleteUI('unigrid_menu', menu=True)

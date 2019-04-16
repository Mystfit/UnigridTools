try:
    from arnold import *
except ImportError:
    pass

def inject_AOV(ass_file, AOV_name):
    AiBegin()
    AiMsgSetConsoleFlags(AI_LOG_ALL)
    AiASSLoad(ass_file, AI_NODE_ALL)

    ######
    AiEnd()

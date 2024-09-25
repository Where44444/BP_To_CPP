import pyperclip
import pathlib
import re
import traceback
from typing import List
####################################################################################
#Designed for copying a single node graph from UE4.27 to the clipboard
#Will create functions for macros
#Problems with compiling goto statements can be fixed by not having multiple execute inputs into a single node, use sequences and macros to avoid it

#Use these as comments on nodes:
#cpp:ignore -> Ignores the node, useful for reducing code from return nodes in macros
#cpp:local -> Use on setting a variable to transform from this->var = 0; to float var = 0;
#cpp:cache -> Use to supress warning about pure function being connected to multiple nodes
####################################################################################

#What category to set in UPROPERTY for this-> variables at the top
variablesCategory = "Scanner" #TODO Implement this

#What Class:: to put before .cpp file function declaration
className = "AW4Database_Funcs"

#Overriden if the blueprint code is a function graph
#Can also be overriden by adding a comment to the start node of your bp graph
functionName = "ScannerTick" 

#Used for directly adding variables inline, if the variable is only declared and used once
flattenCode = True

debug = False
errorTrace = False

#Texts to global replace, called on cpp afterwards
postReplacements = {
    "UW4_InGame_TextBP_C" : "AW4_InGame_Text",
    "UW4_InGame_Text" : "AW4_InGame_Text",
    "TargetVoxelsTransform_0" : "TargetVoxelsTransform",
    "ToggleScannerBP" : "ToggleScanner",
    "W4_Macros_Object:ScannerVoxelWithinBounds" : "ScannerVoxelWithinBounds",
}

postRegexReplacements = {
    #Fixes wrong order of pins to C++ AttachToComponent function, also adds FAttachmentTransformRules constructor
    r"AttachToComponent\((.[^,]*?),(.[^,]*?),(.[^,]*?),(.[^,]*?),(.[^,]*?),(.[^,]*?)\)" : r"AttachToComponent(\1, FAttachmentTransformRules(\3,\4,\5,\6), \2)",
    r"FLinearColor\(\(R=(.*?)G=(.*?)B=(.*?)A=(.*?)\)" : r"FLinearColor(\1\2\3\4)",
    r"FVector2D\(\(X=(.*?)Y=(.*?)\)\)" : r"FVector2D(\1\2)",
}

#Function name replacements
memberNameReplacements = {
    "K2_SetWorldTransform": "SetWorldTransform",
    "K2_SetWorldLocation" : "SetWorldLocation",
    "K2_SetWorldRotation" : "SetWorldRotation",
    "K2_SetActorTransform" : "SetActorTransform",
    "K2_AttachToComponent" : "AttachToComponent",
    "K2_SetRelativeTransform" : "SetRelativeTransform",
    "K2_SetRelativeLocation" : "SetRelativeLocation",
    "K2_SetRelativeRotation" : "SetRelativeRotation",
    "K2_GetComponentLocation" : "GetComponentLocation",
    "K2_GetComponentToWorld" : "GetComponentTransform",
}

memberParentsToUse = {
    "KismetSystemLibrary" : "UKismetSystemLibrary",
    "KismetMathLibrary" : "UKismetMathLibrary",
    "BlueprintMapLibrary" : "UBlueprintMapLibrary",
    "KismetMaterialLibrary" : "UKismetMaterialLibrary",
    "GameplayStatics" : "UGameplayStatics",
    "KismetTextLibrary" : "UKismetTextLibrary",
    "KismetStringLibrary" : "UKismetStringLibrary",
}

replacePin = { #Prefix + Postfix around variable only for functions
    "SetWorldTransform bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"], #The SetWorldTransform node uses a bool instead of the prop Enum
    "SetWorldTransform SweepHitResult" : ["&", ""],
    "SetWorldLocation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"],
    "SetWorldLocation SweepHitResult" : ["&", ""],
    "SetWorldRotation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"],
    "SetWorldRotation SweepHitResult" : ["&", ""],
    "SetActorTransform bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"],
    "SetActorTransform SweepHitResult" : ["&", ""],
    "SetActorLocation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"],
    "SetActorLocation SweepHitResult" : ["&", ""],
    "SetActorRotation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"],
    "SetActorRotation SweepHitResult" : ["&", ""],
    "SetRelativeTransform SweepHitResult" : ["&", ""],
    "SetRelativeTransform bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"], 
    "SetRelativeLocation SweepHitResult" : ["&", ""],
    "SetRelativeLocation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"], 
    "SetRelativeRotation SweepHitResult" : ["&", ""],
    "SetRelativeRotation bTeleport" : ["", " ? ETeleportType::TeleportPhysics : ETeleportType::None"], 
}

Structs = {
    "FTransform" : ["FTransform(", ")"],
    "FVector" : ["FVector(", ")"],
    "FRotator" : ["FRotator(", ")"],
    "FLinearColor" : ["FLinearColor(", ")"],
    "FIntVector" : ["FIntVector(", ")"],
    "FVector2D" : ["FVector2D(", ")"],
}

#Code specifically checks for a " = " in [1] for adding |type x = y|
functionFormat = { #Pin, Operand, Pin, Operand, Pin, Operand, Pin, Operand, ...
    "Multiply_VectorFloat" : ["ReturnValue", " = (", "A", " * ", "B", ")"],
    "Multiply_VectorInt" : ["ReturnValue", " = (", "A", " * ", "B", ")"],
    "Multiply_VectorVector" : ["ReturnValue", " = (", "A", " * ", "B", ")"],
    "Divide_VectorFloat" : ["ReturnValue", " = (", "A", " / ", "B", ")"],
    "Divide_VectorInt" : ["ReturnValue", " = (", "A", " / ", "B", ")"],
    "Divide_VectorVector" : ["ReturnValue", " = (", "A", " / ", "B", ")"],
    "Divide_FloatFloat" : ["ReturnValue", " = (", "A", " / ", "B", ")"],
    "Divide_IntInt" : ["ReturnValue", " = (", "A", " / ", "B", ")"],
    "Subtract_VectorFloat" : ["ReturnValue", " = (", "A", " - ", "B", ")"],
    "Subtract_VectorInt" : ["ReturnValue", " = (", "A", " - ", "B", ")"],
    "Subtract_VectorVector" : ["ReturnValue", " = (", "A", " - ", "B", ")"],
    "Subtract_FloatFloat" : ["ReturnValue", " = (", "A", " - ", "B", ")"],
    "Subtract_IntInt" : ["ReturnValue", " = (", "A", " - ", "B", ")"],
    "GreaterEqual_FloatFloat" : ["ReturnValue", " = (", "A", " >= ", "B", ")"],
    "GreaterEqual_IntInt" : ["ReturnValue", " = (", "A", " >= ", "B", ")"],
    "Greater_FloatFloat" : ["ReturnValue", " = (", "A", " > ", "B", ")"],
    "Greater_IntInt" : ["ReturnValue", " = (", "A", " > ", "B", ")"],
    "LessEqual_FloatFloat" : ["ReturnValue", " = (", "A", " <= ", "B", ")"],
    "LessEqual_IntInt" : ["ReturnValue", " = (", "A", " <= ", "B", ")"],
    "Less_FloatFloat" : ["ReturnValue", " = (", "A", " < ", "B", ")"],
    "Less_IntInt" : ["ReturnValue", " = (", "A", " < ", "B", ")"],
    "EqualEqual_FloatFloat" : ["ReturnValue", " = (", "A", " == ", "B", ")"],
    "EqualEqual_IntInt" : ["ReturnValue", " = (", "A", " == ", "B", ")"],
    "Not_PreBool" : ["ReturnValue", " = !(", "A", ")"],
    "Map_Find" : ["Value", " = ", "TargetMap", "[", "Key", "]"],
    "Map_Keys" : ["TargetMap", ".GetKeys(", "Keys", ")"],
    "Map_Clear" : ["TargetMap", ".Reset()"],
    "Set_Length" : ["ReturnValue", " = ", "TargetSet", ".Num()"],
    "Set_Contains" : ["ReturnValue", " = ", "TargetSet", ".Contains(", "ItemToFind", ")"],
    "Set_Clear" : ["TargetSet", ".Reset()"],
    "Set_Add" : ["TargetSet", ".Add(", "NewItem", ")"],
    "Set_ToArray" : ["Result", " = ", "A", ".Array()"],
    "MakeVector" : ["ReturnValue", " = FVector(", "X", ", ", "Y", ", ", "Z", ")"],
    "Conv_TextToString" : ["ReturnValue", " = ", "InText", ".ToString()"],
    "NotEqual_StrStr" : ["ReturnValue", " = !(", "A", ".Equals(", "B", "))"],
    "NotEqual_ObjectObject" : ["ReturnValue", " = (", "A", " != ", "B", ")"],
    "Equal_StrStr" : ["ReturnValue", " = ", "A", ".Equals(", "B", ")"],
    "GetSubstring" : ["ReturnValue", " = ", "SourceString", ".Mid(", "StartIndex", ", ", "Length", ")"]
}

SubPinGetters = {
    "FTransform" : {"Location" : "GetLocation()",
                    "Rotation" : "GetRotation().Rotator()", 
                    "Scale" : "GetScale3D()",
                    }
}

VariableGetsToFunctions = {
    "UStaticMeshComponent StaticMesh" : "GetStaticMesh()",
    "AActor RootComponent" : "GetRootComponent()",
}

class Variable():
    def __init__(self) -> None:
        self.name : str = ""
        self.tab : int = 0
        self.pure : bool = False

vars : dict[str : list[str]]= {} #var -> [var, operator, var, operator, ...]
pinsToVariables : dict[str : Variable] = {} #node.name pinId -> [variable name, tab]
cpp = ""
currentTab = 0

def findPersistentOption(option):
    global persistent
    return persistent[persistent.find(option) :].split("=")[1].split(",")[0]

def writeToPersistent(new):
    f = open("BP_to_CPP_Persistent.txt", "w")
    f.write(new)
    f.close()

persistent = ""
f = open("BP_to_CPP_Persistent.txt", "r")
if f.readable():
    persistent = f.read()
    f.close()
else:
    f.close()
    writeToPersistent("currentVarInc=0")

#Will be used to generate variables like var0, branch0, skip0
# currentVarInc = int(findPersistentOption("currentVarInc"))
currentVarInc = 0

primitives = {"int", "float", "bool"}
# mathSymbols = {" + ", " - ", " * ", " / "}

#Node Types:
Tunnel = 1
VariableGet = 2
VariableSet = 3
Function = 4
Macro = 5
ArrayFunction = 6
GetArrayItem = 7
Cast = 8
IfThen = 9
Sequence = 10
Indent = 11
Unindent = 12
Math = 13
MakeArray = 14
Knot = 15
FunctionResult = 16
FunctionEntry = 17
BreakStruct = 18

#Array Function Types:
ArraySet = 1

class PinConnection():
    def __init__(self):
        self.nodeName : str = ""
        self.PinId : str = ""

class Pin():
    def __init__(self):
        self.PinId : str = ""
        self.isExec : bool = False
        self.isInput : bool = False
        self.isOutput : bool = False
        self.type : str = "" #exec, FName, int, float
        self.DefaultValue : str = ""
        self.DefaultObject : str = ""
        self.connections : List[PinConnection] = []
        self.PinName : str = ""
        self.isPointer : bool = False
        self.ContainerType : str = "None" #Map
        self.TerminalCategory : str = "" #FString
        self.isTerminalPointer : bool = False
        self.SubPinCons : List[PinConnection] = []
        self.SubPins : List[Pin] = []
        self.Enum : str = ""
        self.node : Node = None
        self.ParentPin : Pin = None

    def connected(self):
        for con in self.connections:
            if getNode(con).NodeComment.find("cpp:ignore") == -1:
                return True
        for subPin in self.SubPins:
            if subPin.connected():
                return True
        return False
    #Returns first connection
    def con(self):
        return self.connections[0]
    
    def getVar(self):
        if self.isInput:
            return getInPinToVariable(self)
        else:
            return getOutPinToVariable(self)
    
    def isSubPin(self):
        for pin in self.node.pins:
            for subPin in pin.SubPins:
                if subPin.PinId == self.PinId:
                    return True
        return False
    
    def inUse(self):
        for node in nodes.values():
            for pin in node.pins:
                for con in pin.connections:
                    if self.node.Name == con.nodeName and self.PinId == con.PinId:
                        return True
            for pin in node.subPins:
                for con in pin.connections:
                    if self.node.Name == con.nodeName and self.PinId == con.PinId:
                        return True
        for subPin in self.SubPins:
            if subPin.inUse():
                return True
        return False
    
    def getSubName(self):
        if not self.isSubPin():
            error("Attempting to get subname from non-subpin! " + self.PinName)
        if self.ParentPin.type in SubPinGetters:
            getters = SubPinGetters[self.ParentPin.type]
            for key, val in getters.items():
                if self.PinName.find(key) != -1:
                    return val
                
        index = len(self.PinName) - self.PinName[::-1].find("_") #Find index in reversed string, then find inverse index
        return self.PinName[index : ]
    
    def hasSubPins(self):
        return not isEmpty(self.SubPins)
    
    #Intended for finding how many different nodes connected to
    def numUniqueNodeConnections(self):
        keys = set()
        for con in self.connections:
            keys.add(con.nodeName)
        for subPin in self.SubPins:
            for con in subPin.connections:
                keys.add(con.nodeName)
        return len(keys)

class Node():
    def __init__(self):
        self.type : int = 0
        self.Name : str = ""
        self.pins : List[Pin] = []
        self.subPins : List[Pin] = []
        self.macroType : int = 0
        self.arrayFunctionType : int = 0
        self.MemberParent : str = "" #KismetMathLibrary
        self.MemberName : str = "" #InvertTransform
        self.postCode : str = "" #Used for adding labelX {
        self.prefixCode : str = "" #Used for adding labelX {
        self.MacroGraph : str = "" #StandardMacros:ForEachLoop
        self.ResolvedWildcardType : str = "" #StaticMeshComponent
        self.breakVar : str = "" #break0 | Used for for loops with break
        self.NodeComment : str = ""
        self.LocalVariables : List[Pin] = []

    def hasInputExec(self):
        for pin in self.pins:
            if pin.isExec and pin.isInput and len(pin.connections) != 0:
                return True
        return False
    
    def hasOutputExec(self):
        for pin in self.pins:
            if pin.isExec and pin.isOutput and len(pin.connections) != 0:
                return True
        return False

    #Says if the node belongs to the class we're working in, does not require resolving references
    def selfIsContext(self):
        if not self.getSelfInput():
            return True
        for pin in self.pins:
            if pin.PinName == "self" and len(pin.connections) == 0:
                return True
        return False

    #Node could be a local variableGet in a function, which has no self pin
    def getSelfInput(self) -> Pin:
        for pin in self.pins:
            if pin.isInput and pin.PinName == "self":
                return pin
        # error("Could not find self input! " + self.Name)
        return None
    
    def variableGetPin(self) -> Pin:
        for pin in self.pins:
            if pin.isOutput and not pin.isExec:
                return pin
        error("Could not find variable out pin for node! " + self.Name)

    def variableSetPin(self) -> Pin:
        for pin in self.pins:
            if pin.isInput and not pin.isExec and pin.PinName != "self":
                return pin
        error("Could not find variable set pin for node! " + self.Name)
        
    def breakInPin(self) -> Pin:
        for pin in self.pins:
            if pin.isInput and not pin.isExec and pin.PinName != "self":
                return pin
        error("Could not find variable set pin for node! " + self.Name)

    def getCastOutputPin(self) -> Pin:
        for pin in self.pins:
            if pin.isOutput and len(pin.PinName) > 1 and pin.PinName[:2] == "As":
                return pin
        error("Cast output pin not found! " + self.Name)
        return None
    
    def getThenOutput(self) -> Pin:
        for pin in self.pins:
            if pin.isOutput and pin.isExec and pin.connected():
                return pin
        return None
    
    def getPin(self, PinName) -> Pin:
        for pin in self.pins:
            if pin.PinName == PinName:
                return pin
        for pin in self.subPins:
            if pin.PinName == PinName:
                return pin
        # error("Pin not found! " + self.Name + " " + PinName)
        return None

    def getPinFromID(self, id) -> Pin:
        for pin in self.pins:
            if pin.PinId == id:
                return pin
        for pin in self.subPins:
            if pin.PinId == id:
                return pin
        error("Could not find pin on node! " + self.Name + " | " + id)
        return None

def getDefaultValue(pin : Pin):
    if line.find("DefaultValue=") != -1:
        struct = None
        if pin.type in Structs:
            struct = Structs[pin.type]
            pin.DefaultValue = struct[0] + cleanBP(lFind4("DefaultValue")) + struct[1]
        else:
            pin.DefaultValue = cleanBP(lFind4("DefaultValue"))
    else:
        if pin.type == "FTransform":
            pin.DefaultValue = "FTransform::Identity"
        if pin.type == "FVector":
            pin.DefaultValue = "FVector::ZeroVector"
        if pin.type == "FIntVector":
            pin.DefaultValue = "FIntVector::ZeroValue"
        if pin.type == "FVector2D":
            pin.DefaultValue = "FVector2D::ZeroVector"
        if pin.type == "FRotator":
            pin.DefaultValue = "FRotator::ZeroRotator"
        if pin.type == "float" or pin.type == "int":
            pin.DefaultValue = "0"
        if pin.type == "bool":
            pin.DefaultValue = "false"

startNode : Node = None
endNode : Node = None

#Return FName for name, FString for string, etc.
def getTypeFromBP(bptype, objectTypeKeyword): 
    if bptype == "exec":
        return "exec"
    elif bptype == "object" and objectTypeKeyword:
        t = cleanBP(getDotSeparatedName(lFind(objectTypeKeyword)))
        if t.lower().find("component") != -1:
            return "U" + t
        elif t.lower().find("actor") != -1:
            return "A" + t
        else:
            return "U" + t
    elif bptype == "struct" and objectTypeKeyword:
        return "F" + cleanBP(lFind(objectTypeKeyword).split(".")[1])
    elif bptype == "name":
        return "FName"
    elif bptype == "string":
        return "FString"
    elif bptype == "byte" and objectTypeKeyword:
        return cleanBP(lFind(objectTypeKeyword).split(".")[1])
    elif bptype == "interface":
        return "auto"
    elif bptype == "class":
        return "FFieldClass"
    elif bptype == "text":
        return "FText"
    elif bptype in primitives:
        return bptype #int, float, bool, etc.
    else:
        error("Unknown pin category! " + bptype + "\n" + line)

def easyMacroCall(node : Node):
    code = ""
    suffix = ""
    outPin : Pin = None
    paramPins = []
    resultPins = []
    for pin in node.pins:
        if pin.isExec:
            if pin.isOutput:
                outPin = pin
        else:
            if pin.isInput:
                code += resolveReferences(pin)
                paramPins.append(pin)
            else:
                resultPins.append(pin)
                suffix += addOutPinToVariable(pin, [])
    if not isEmpty(resultPins):
        code += tabs()
    for pin in resultPins:
        code += typ(pin) + getOutPinToVariable(pin) + "; "
    if not isEmpty(resultPins):
        code += "\n"
    code += tabs() + node.MacroGraph + "("
    for pin in paramPins:
        code += getInPinToVariable(pin) + ", "
    for pin in resultPins:
        code += getOutPinToVariable(pin) + ", "
    code = noComma(code) + ");\n"
    if outPin and outPin.connected():
        addNodeToStack(outPin.con())
    return code + suffix

def error(message):
    print(message)
    if errorTrace:
        traceback.print_stack() 
    exit()

def arrayToStr(array):
    str0 = ""
    for item in array:
        str0 += item
    return str0

def addCPP(code, *args):
    """args[0] = debug description : str"""
    global cpp
    if debug and len(args) > 0:
        cpp += "-----" + args[0] + "------\n"
    cpp += code

def addUnindentToStack(*suffix):
    node = Node()
    node.type = Unindent
    if len(suffix) > 0:
        node.postCode = suffix[0]
    stack.append(node)
    connectionStack.append(None)

def upperFirst(s):
    return s.replace(s[0], s[0].upper(), 1)

def addNodeToStack(connection : PinConnection, *args):
    """args[0] = prefix code"""

    if connection.nodeName in nodes:
        node = nodes[connection.nodeName]
        if len(args) > 0:
            node.prefixCode += args[0]

        stack.append(node)
        connectionStack.append(connection)
    else:
        error("Node does not exist in nodes map! " + connection.nodeName)

#Used for finding simple key=Value,
def lFind(key, *args):
    if len(args) > 0:
        line = args[0]
    else:
        line = currentLine
    index = line.find(key + "=")
    if index != -1:
        line = line[index:]
        return line.split("=", 1)[1].split(",")[0]
    error(key + " not found on line " + str(inc) + "!")
    return None

#Used for finding array of connected pins
def lFind2(key):
    index = currentLine.find(key + "=")
    if index != -1:
        line = currentLine[index:]
        list = line.split("=(", 1)[1].split(")")[0].split(",")
        for i in list:
            if(i==""):
                list.remove(i)
        return list
    error(key + " not found on line " + str(inc) + "!")
    return None

#Used for finding simple key=Value",
def lFind3(key, *args):
    if len(args) > 0:
        line = args[0]
    else:
        line = currentLine
    index = line.find(key + "=")
    if index != -1:
        line = line[index:]
        return line.split("=", 1)[1].split(" ")[0]
    error(key + " not found on line " + str(inc) + "!")
    return None

#Used for finding simple key=Value",
def lFind4(key, *args):
    if len(args) > 0:
        line = args[0]
    else:
        line = currentLine
    index = line.find(key + "=")
    if index != -1:
        line = line[index:]
        return line.split("=", 1)[1].split("\",")[0]
    error(key + " not found on line " + str(inc) + "!")
    return None
    
def cleanBP(str0):
    if str0[0] == "(":
        str0 = str0[1:]
    if str0[0] == "\'":
        str0 = str0[1:]
    if str0[0] == "\"":
        str0 = str0[1:]
    if str0[-1] == ")":
        str0 = str0[:-1]
    if str0[-1] == "\'":
        str0 = str0[:-1]
    if str0[-1] == "\"":
        str0 = str0[:-1]
    str0 = str0.replace("\\r\\n", "\n")
    return str0

def hasComma(str0):
    if len(str0) > 0 and str0[-1] == ",":
        return True
    if len(str0) > 1 and str0[-2] == ",":
        return True
    return False

def noComma(str0):
    if str0[-1] == ",":
        return str0[:-1]
    elif str0[-1] == " " and str0[-2] == ",":
        return str0[:-2]
    return str0

def getNode(connection : PinConnection) -> Node:
    global nodes
    if connection.nodeName in nodes:
        return nodes[connection.nodeName]
    error("Could not find node in nodes! " + connection.nodeName)
    return None

def getVarInc():
    global currentVarInc
    currentVarInc += 1
    return str(currentVarInc)

# def resolveVariable(key : str):
#     var : Variable = pinsToVariables[key]
#     if var.pure: #Pure
#         line = ""
#         if not var.name in vars:
#             return var.name #Likely a local or member variable
#         value = vars[var.name]
#         for i in range(len(value)):
#             if i % 2 == 0: #Var
#                 if value[i] != "":
#                     resultFound = False
#                     for key0, var0 in pinsToVariables.items():
#                         if var0.name == value[i]:
#                             line += resolveVariable(key0)
#                             resultFound = True
#                             break
#                     if not resultFound:
#                         line += value[i] #Likely a string literal or local or member variable
#             else: #Operator
#                 line += value[i]
#         return "(" + line + ")"
#     else:
#         return var.name


def getInPinToVariable(pin : Pin, *args):
    """Provide input pin. returns variable for output it's connected to\n
    args[0] = PinConnection"""
    if pin.isOutput:
        error("getInPinToVariable was provided an output pin! " + pin.PinId)
    if pin.hasSubPins():
        return handleInputSubPins(pin)
    if not pin.connected():
        if pin.ContainerType == "Array":
            return "{}"
        if pin.isPointer:
            if pin.PinName == "self" or pin.PinName == "WorldContextObject":
                return "this"
            elif pin.type == "FFieldClass" and pin.DefaultObject != "":
                return pin.DefaultObject + "::StaticClass()"
            else:
                return "nullptr"
        if pin.type == "FString" or pin.type == "FName":
            return "\"" + pin.DefaultValue + "\""
        return pin.DefaultValue
    connection = pin.con()
    if len(args) > 0:
        connection = args[0]
    key = connection.nodeName + " " + connection.PinId
    if key in pinsToVariables:
        # return resolveVariable(key)
        return pinsToVariables[key].name
    else:
        error("Input pin not found in pinsToVariable dictionary! " + key + " | " + pin.PinName)
    return ""

def getOutPinToVariable(pin : Pin):
    """Provide output pin"""
    if pin.isInput:
        error("getOutPinToVariable was provided an input pin! " + pin.PinId)
    key = pin.node.Name + " " + pin.PinId
    if key in pinsToVariables:
        # return resolveVariable(key)
        return pinsToVariables[key].name
    else:
        error("Output pin not found in pinsToVariable dictionary! " + key + " | " + pin.PinName)
    return ""

def addOutPinToVariable(pin : Pin, valueArray : List[str], *args):
    """pin = Output pin that should be tied to a variable\n
    valueArray = array : str of right side of = |var, operator, var, operator, ...|\n
    args[0] = override variable name\n
    This also returns suffix code needed for handling subpins, add this after adding parent variable declaration code\n
    This, the Pin class, and Node class should be the only functions that work with subpins"""
    if pin.isInput:
        error("addOutPinToVariable was provided an input pin! " + pin.PinId)
    
    if len(args) > 0:
        variableName = args[0]
    else:
        variableName = "var" + getVarInc()
    
    key = pin.node.Name + " " + pin.PinId
    if key in pinsToVariables:
        error("Key: |" + key + "| Already in pinsToVariables dictionary!")
    var = Variable()
    var.name = variableName
    var.tab = currentTab
    var.pure = not pin.node.hasInputExec()
    pinsToVariables[key] = var
    if not isEmpty(valueArray):
        vars[variableName] = valueArray

    code = ""
    suffixCode = ""
    for subPin in pin.SubPins:
        if subPin.connected():
            value = [getOutPinToVariable(pin), ".", subPin.getSubName()]
            suffixCode += addOutPinToVariable(subPin, value)
            code += tabs() + typ(subPin) + getOutPinToVariable(subPin) + " = " + arrayToStr(value) + ";\n"

    return code + suffixCode

def handleInputSubPins(pin : Pin): 
    """Returns inline struct, e.g. |FVector(var1, 0, 0)|"""

    line = ""
    if pin.isOutput:
        error("handleInputSubPins was provided an output pin!")
    if not pin.type in Structs:
        error("Structs missing type! " + pin.type)
    struct = Structs[pin.type]
    line += struct[0]
    for subPin in pin.SubPins:
        if subPin.hasSubPins():
            line += handleInputSubPins(subPin) + ", "
        else:
            line += getInPinToVariable(subPin) + ", "
    line = noComma(line) + struct[1]
    return line


def getFunctionFormat(node : Node, key : str):
    line = ""
    suffix = ""
    format = functionFormat[key]
    outPin = None
    if len(format) > 1 and format[1].find("=") != -1:
        if format[1].find(" = ") == -1:
            error("Expecting \" = \" in format but found \"" + format[1] + "\"")
        outPin = node.getPin(format[0])
    vars0 = []
    ppins = []
    operands = []
    for i, item in enumerate(format):
        if i % 2 == 0:
            pin = node.getPin(item)
            if pin == None:
                error("Function format " + key + " could not find pin! " + item)
            ppins.append(pin)
        else:
            if outPin and item.find(" = ") != -1:
                operands.append(item.replace(" = ", ""))
            else:
                operands.append(item)

    lineAdded = False
    for ppin in ppins:
        if ppin.isOutput:
            if ppin != outPin:
                suffix += addOutPinToVariable(ppin, [])
                if not lineAdded:
                    line += tabs()
                line += typ(ppin) + getOutPinToVariable(ppin) + "; "
                lineAdded = True
        if ppin == outPin:
            vars0.append("")
        else:
            vars0.append(ppin.getVar())

    if lineAdded:
        line += "\n"

    line += tabs()

    next = True
    inc = 0
    value = []
    while next:
        next = False
        if inc < len(vars0):
            next = True
            value.append(vars0[inc])
        if inc < len(operands):
            next = True
            value.append(operands[inc])
        inc += 1
    
    outVar = ""
    if outPin:
        addOutPinToVariable(outPin, value)
        outVar = typ(outPin) + outPin.getVar() + " = "

    line += outVar + arrayToStr(value) + ";\n"
    return line + suffix

def func(node : Node, pins : Pin, params : List[str], *args):
    """Builds the function e.g. SetVisibility(var1, true, false)
    args[0] = PinConnection"""
    selfPin = node.getSelfInput()
    owner = ""
    if node.selfIsContext():
        owner = ""
    elif selfPin:
        if len(args) > 0:
            owner = getInPinToVariable(selfPin, args[0])
        else:
            owner = getInPinToVariable(selfPin)

    f = []

    if node.MemberParent in memberParentsToUse:
        f.append("")
        f.append(memberParentsToUse[node.MemberParent] + "::")
    elif owner != "":
        f.append(owner)
        f.append(getRelator(selfPin))

    if isEmpty(f):
        f.append("")
        f.append("")
    f[-1] += node.MemberName + "("

    paramStack = []
    for idx, param in enumerate(params):
        suffix = ""
        if len(paramStack) > 0:
            suffix += paramStack.pop()
        pin = pins[idx]

        prefix2 = ""
        suffix2 = ""
        if param == pin.DefaultValue and pin.Enum != "":
            prefix2 += pin.Enum + "::"

        if param == pin.DefaultValue and pin.type == "bool":
            param = param.lower()

        key = node.MemberName + " " + pin.PinName
        if key in replacePin:
            options = replacePin[key]
            f[-1] += options[0] + prefix2
            f.append(param)
            f.append(suffix2 + options[1] + ", ")
        else:
            f[-1] += prefix2
            f.append(param)
            f.append(suffix2 + ", ")

        if hasComma(f[-1]):
            f[-1] = noComma(f[-1]) + suffix + ", "
        else:
            f[-1] += suffix
    f[-1] = noComma(f[-1]) + ")"
    return f

def getFunctionCode(node : Node):
    selfPin = node.getSelfInput()
    line = ""
    suffix = ""
    if selfPin:
        line += resolveReferences(selfPin)

    returnPin = None
    for pin in node.pins:
        if pin != selfPin and not pin.isExec and pin.isInput:
            line += resolveReferences(pin)
        if pin.isOutput and pin.PinName == "ReturnValue":
            returnPin = pin
    if debug:
        line += "--getFunctionCode--\n"

    #User overriden function format
    if node.MemberName in functionFormat:
        line += getFunctionFormat(node, node.MemberName)
        return line
    
    useReturnPin = False
    if returnPin:
        useReturnPin = returnPin.inUse()

    #Check return by reference pins, add pre-references (FName var0, UStaticMesh* var1, etc.)
    lineAdded = False
    for pin in node.pins:
        if pin != selfPin and not pin.isExec and pin.isOutput and pin.PinName != "ReturnValue":
            suffix += addOutPinToVariable(pin, [])
            if not lineAdded:
                line += tabs()
            line += typ(pin) + getOutPinToVariable(pin) + "; "
            lineAdded = True
    if lineAdded:
        line += "\n"


    params = []
    pins = []
    for pin in node.pins:
        if pin != selfPin and not pin.isExec and pin.isInput:
            params.append(getInPinToVariable(pin))
            pins.append(pin)
        #Add return by reference vars to function call (var0, var1, etc)
        if not pin.isExec and pin.isOutput and pin.PinName != "ReturnValue":
            params.append(getOutPinToVariable(pin))
            pins.append(pin)

    if useReturnPin:
        value = func(node, pins, params)
        suffix += addOutPinToVariable(returnPin, value)
        line += tabs() + typ(returnPin) + getOutPinToVariable(returnPin) + " = " + arrayToStr(value) + ";\n"
    else:
        if selfPin and not isEmpty(selfPin.connections):
            for con in selfPin.connections:
                line += tabs() + arrayToStr(func(node, pins, params, con)) + ";\n"
        else:
            line += tabs() + arrayToStr(func(node, pins, params)) + ";\n"
    return line + suffix

def cleanVar(name):
    name = name.replace(" ", "")
    name = name.replace(name[0], name[0].upper(), 1)
    return name

def cleanFunction(name):
    name = name.replace(" ", "")
    return name

def tabs():
    global currentTab
    tab = ""
    for i in range(currentTab):
        tab += "\t"
    return tab

def typ(pin : Pin):
    if pin.ContainerType == "Array":
        if pin.isPointer:
            return "TArray<" + pin.type + "*> "
        else:
            return "TArray<" + pin.type + "> "
    if pin.ContainerType == "Set":
        if pin.isPointer:
            return "TSet<" + pin.type + "*> "
        else:
            return "TSet<" + pin.type + "> "
    if pin.ContainerType == "Map":
        if pin.isPointer:
            if pin.isTerminalPointer:
                return "TMap<" + pin.type + "*, " + pin.TerminalCategory + "*> "
            else:
                return "TMap<" + pin.type + "*, " + pin.TerminalCategory + "> "
        else:
            if pin.isTerminalPointer:
                return "TMap<" + pin.type + ", " + pin.TerminalCategory + "*> "
            else:
                return "TMap<" + pin.type + ", " + pin.TerminalCategory + "> "
        
    if pin.isPointer:
        return pin.type + "* "
    else:
        return pin.type + " "
    
def getRelator(pin : Pin):
    if pin.isPointer:
        return "->"
    return "."

def addTwoPinBranch(node : Node):
    global currentTab
    line = ""
    suffix = ""
    if node.type == Cast:
        out1 = node.getPin("then")
        out2 = node.getPin("CastFailed")
        conditionPin = node.getPin("Object")
        line += resolveReferences(conditionPin)
        outPin = node.getCastOutputPin()
        value = ["", "Cast<" + outPin.type + ">(", getInPinToVariable(conditionPin), ")"]
        suffix += addOutPinToVariable(outPin, value)
        line += tabs() + typ(outPin) + getOutPinToVariable(outPin) + " = " + arrayToStr(value) + ";\n"
        condition = getOutPinToVariable(outPin)
    elif node.MacroGraph == "StandardMacros:IsValid":
        out1 = node.getPin("Is Valid")
        out2 = node.getPin("Is Not Valid")
        conditionPin = node.getPin("InputObject")
        line += resolveReferences(conditionPin)
        condition = getInPinToVariable(conditionPin)
    elif node.type == IfThen:
        out1 = node.getPin("then")
        out2 = node.getPin("else")
        conditionPin = node.getPin("Condition")
        line += resolveReferences(conditionPin)
        condition = getInPinToVariable(conditionPin)

    if not out1.connected():
        out1 = None
    if not out2.connected():
        out2 = None
    if out1 and out2:
        addUnindentToStack()
        addNodeToStack(out2.con())
        addUnindentToStack("else {")
        addNodeToStack(out1.con(), tabs() + "if(" + condition + ") {\n")
    elif out1:
        addUnindentToStack()
        addNodeToStack(out1.con())
        line += tabs() + "if(" + condition + ") {\n"
        addTab()
    elif out2:
        addUnindentToStack()
        addNodeToStack(out2.con())
        line += tabs() + "if(!(" + condition + ")) {\n"
        addTab()
    return line + suffix

def addTab():
    global currentTab
    currentTab += 1

def removeTab():
    global currentTab
    currentTab -= 1
    keysToRemove = []
    for key, var in pinsToVariables.items():
        if var.tab > currentTab:
            keysToRemove.append(key)

    for key in keysToRemove:
        pinsToVariables.pop(key)

def addBreak(node):
    b = "break_" + getVarInc()
    node.breakVar = b
    return b

def getBreak(node):
    if node.breakVar == "":
        error("Node missing breakVar! " + node.Name)
    return node.breakVar

def isEmpty(array):
    return len(array) == 0

# def addBranch(connection : PinConnection, *nameArg):
#     key = connection.nodeName + " " + connection.PinId
#     if key in branches:
#         error("Key " + key + " already exists in branches!")
#     if isEmpty(nameArg):
#         name = "branch" + getVarInc()
#     else:
#         name = nameArg[0]
    
#     branches[key] = name
#     return name

# def getBranch(connection : PinConnection):
#     key = connection.nodeName + " " + connection.PinId
#     if key in branches:
#         return branches[key]
#     return None

# def addBranchNodeAdded(connection : PinConnection):
#     key = connection.nodeName + " " + connection.PinId
#     if key in branchesAdded:
#         error("Key " + key + " already exists in branches added!")
#     branchesAdded[key] = True

# def getBranchNodeAdded(connection : PinConnection):
#     key = connection.nodeName + " " + connection.PinId
#     if key in branchesAdded:
#         return True
#     return False

#Name may or may not have . in it, find the name after the dot if there is one
def getDotSeparatedName(name):
    name = name.replace("BlueprintGeneratedClass", "")
    name = name.replace("EdGraph", "")
    names = name.split(".")
    if len(names) > 1:
        return names[1]
    else:
        return names[0]
    

def resolveKnot(connection : PinConnection, input : bool):
    node = getNode(connection)
    if node.type == Knot:
        if input:
            if isEmpty(node.pins[0].connections):
                error("Unconnected reroute node! " + node.Name)
            return resolveKnot(node.pins[0].con(), input) #Will return first of many nodes if it's a grafted execution knot
        else: #Output
            if isEmpty(node.pins[1].connections):
                error("Unconnected reroute node! " + node.Name)
            return resolveKnot(node.pins[1].con(), input) #Will return first of many nodes if it's a branching data knot
    else:
        return connection

def resolveReferences(pin : Pin, *args):
    """Intended to generate code for all the variables needed for current node\n
    Handles subPins\n"""
    if pin.isExec:
        return ""
    if pin.isOutput:
        return ""
    code = ""
    suffix = ""
    for subPin in pin.SubPins:
        code += resolveReferences(subPin)
    if len(pin.connections) == 0:
        return code + suffix
    
    if len(args) == 0:
        for con in pin.connections: #Handle multiple inputs into data pins
            code += resolveReferences(pin, con)
        return code
    connection = args[0]
    if not connection.nodeName + " " + connection.PinId in pinsToVariables:
        node0 : Node = getNode(connection)
        #Function is only responsible for adding one output variable for current node and pin
        #Need to add code for specifying variable if variable is not already defined in context
        if node0.type == VariableGet:
            outPin = node0.variableGetPin()
            if node0.selfIsContext(): #Reached end of chain, node does not have any more references to resolve
                debugDesc = ""
                if debug:
                    debugDesc = "--Resolve VariableGet Self Context--\n"
                suffix += addOutPinToVariable(outPin, [], cleanVar(outPin.PinName)) #output pin
                return debugDesc + code + suffix
            else: #Need to resolve node going left
                selfPin = node0.getSelfInput()
                owner = ""
                key = ""
                if selfPin:
                    code += resolveReferences(selfPin)
                    owner = getInPinToVariable(selfPin)
                    key = selfPin.type + " " + outPin.PinName
                if debug:
                    code += "--Resolve VariableGet Other Context--\n"
                value = []
                relator = ""
                if owner != "":
                    relator = "->"
                if key in VariableGetsToFunctions:
                    value = [owner, relator + VariableGetsToFunctions[key]]
                else:
                    value = [owner, relator + cleanVar(outPin.PinName)]
                suffix += addOutPinToVariable(outPin, value)
                code += tabs() + typ(outPin) + getOutPinToVariable(outPin) + " = " + arrayToStr(value) + ";\n"
        elif node0.type == Function: #Most likely a pure function
            code += getFunctionCode(node0)
        elif node0.type == VariableSet:
            outPin = node0.variableGetPin()
            if node0.selfIsContext(): #Reached end of chain, node does not have any more references to resolve
                suffix += addOutPinToVariable(outPin, [], cleanVar(node0.MemberName)) #output pin
                return code + suffix
            else: #Need to resolve node going left
                selfPin = node0.getSelfInput()
                owner = ""
                relator = ""
                if selfPin:
                    code += resolveReferences(selfPin)
                    owner = getInPinToVariable(selfPin)
                    relator = "->"
                if debug:
                    code += "--Resolve VariableSet--\n"
                value = [owner, relator + cleanVar(node0.MemberName)]
                suffix += addOutPinToVariable(outPin, value)
                code += tabs() + typ(outPin) + getInPinToVariable(pin) + " = " + arrayToStr(value) + ";\n"
        elif node0.type == GetArrayItem:
            arrayPin = None
            dimensionPin = None
            outPin = None
            for pin0 in node0.pins:
                if pin0.isInput and pin0.PinName == "Array":
                    arrayPin = pin0
                elif pin0.isInput and pin0.PinName == "Dimension 1":
                    dimensionPin = pin0
                elif pin0.isOutput and pin0.PinName == "Output":
                    outPin = pin0
            if not arrayPin or not dimensionPin or not outPin:
                error("Missing array/dimension/out pin for node! " + node0.Name)
            code += resolveReferences(arrayPin)
            code += resolveReferences(dimensionPin)
            value = [getInPinToVariable(arrayPin), "[" , getInPinToVariable(dimensionPin) , "]"]
            suffix += addOutPinToVariable(outPin, value)
            if debug:
                code += "--Resolve GetArrayItem--\n"
            code += tabs() + typ(outPin) + getOutPinToVariable(outPin) + " = " + arrayToStr(value) + ";\n"
        elif node0.type == Math:
            outPin = None
            for pin in node0.pins:
                if pin.isInput and pin.PinName != "self":
                    code += resolveReferences(pin)
                if pin.PinName == "ReturnValue":
                    outPin = pin
            if not outPin:
                error("Could not find return pin on math node! " + node0.Name)
            operator = ""
            if node0.MemberName.find("Multiply") != -1:
                operator = " * "
            elif node0.MemberName.find("Add") != -1:
                operator = " + "
            elif node0.MemberName.find("BooleanAND") != -1:
                operator = " && "
            elif node0.MemberName.find("BooleanOR") != -1:
                operator = " || "
            else:
                error("Could not resolve math type! " + node0.MemberName + " | " + node0.Name)
            if debug:
                code += "--Resolve Math--\n"
            value = []
            for pin in node0.pins:
                if pin.isInput and pin.PinName != "self":
                    value.append(getInPinToVariable(pin))
                    value.append(operator)
            value.pop() #Remove extra operator
            suffix += addOutPinToVariable(outPin, value)
            code += tabs() + typ(outPin) + getOutPinToVariable(outPin) + " = " + arrayToStr(value) + ";\n"
        elif node0.type == MakeArray:
            outPin = None 
            for pin in node0.pins:
                if pin.isInput:
                    code += resolveReferences(pin)
                else:
                    outPin = pin
            if not outPin:
                error("Could not find return pin on make array node! " + node0.Name)
            if debug:
                code += "--Resolve Make Array--\n"
            value = ["", "{"]
            for pin in node0.pins:
                if pin.isInput:
                    value.append(getInPinToVariable(pin))
                    value.append(", ")
            value[-1] = "}" #Remove extra comma
            suffix += addOutPinToVariable(outPin, []) #Causes errors when it flattens code to {a, b, c}[i1], so keep this as a separate variable
            code += tabs() + typ(outPin) + getOutPinToVariable(outPin) + " = " + arrayToStr(value) + ";\n"
        elif node0.type == Macro:
            if node0.MacroGraph in functionFormat:
                for pin in node0.pins:
                    if not pin.isExec and pin.isInput:
                        code += resolveReferences(pin)
                if debug:
                    code += "--Resolve Macro | Function Format--\n"
                code += getFunctionFormat(node0, node0.MacroGraph)
            elif node0.MacroGraph == "W4_Macros_Object:FloatCurve":
                curvePin = node0.getPin("Curve")
                timePin = node0.getPin("Time")
                resultPin = node0.getPin("Result")
                metPin = node0.getPin("Target Met")
                code += resolveReferences(curvePin)
                code += resolveReferences(timePin)
                if debug:
                    code += "--Resolve Macro | Float Curve--\n"
                if metPin.connected():
                    suffix += addOutPinToVariable(resultPin, [])
                    value = ["", "W4::floatCurve(", getInPinToVariable(curvePin), ", " , getInPinToVariable(timePin), ", ", getOutPinToVariable(resultPin), ")"]
                    suffix += addOutPinToVariable(metPin, value)
                    code += tabs() + "float " + getOutPinToVariable(resultPin) + ";\n"
                    code += tabs() + "bool " + getOutPinToVariable(metPin) + " = " + arrayToStr(value) + ";\n"
                else:
                    value = [getInPinToVariable(curvePin), "->GetFloatValue(", getInPinToVariable(timePin), ")"]
                    suffix += addOutPinToVariable(resultPin, value)
                    code += tabs() + "float " + getOutPinToVariable(resultPin) + " = " + arrayToStr(value) + ";\n"
            elif node0.MacroGraph == "W4_Macros_Object:AddIntVector":
                v1Pin : Pin = node0.getPin("V1")
                v2Pin : Pin = node0.getPin("V2")
                resultPin : Pin = node0.getPin("Result")
                code += resolveReferences(v1Pin)
                code += resolveReferences(v2Pin)
                if debug:
                    code += "--Resolve Macro | AddIntVector--\n"
                value = [getInPinToVariable(v1Pin), " + ", getInPinToVariable(v2Pin)]
                suffix += addOutPinToVariable(resultPin, value)
                code += tabs() + "FIntVector " + getOutPinToVariable(resultPin) + " = " + arrayToStr(value) + ";\n"
            # elif node0.MacroGraph in EasyMacroCalls:
            else:
                if debug:
                    code += "--Resolve Macro | Easy Macro Call--\n"
                code += easyMacroCall(node0)
            # else:
                # error("Unhandled macro graph for resolving references! " + node0.MacroGraph)
        elif node0.type == BreakStruct:
            inPin = node0.breakInPin()
            code += resolveReferences(inPin)
            if debug:
                code += "--Resolve BreakStruct--\n"
            for pin in node0.pins:
                if pin.isOutput:
                    if pin.connected():
                        value = [getInPinToVariable(inPin), ".", cleanVar(pin.PinName)]
                        suffix += addOutPinToVariable(pin, value)
                        code += tabs() + typ(pin) + pin.getVar() + " = " + arrayToStr(value) + ";\n"
        else:
            error("Unhandled node type for resolving references! Type " + str(node0.type) + " | " + node0.Name)

    return code + suffix



# Read the clipboard content
clipboard_content = pyperclip.paste()

lines = clipboard_content.split("\r\n")

nodes = {}
inc = 1
currentLine = ""
for line in lines:
    currentLine = line
    if line.find("Begin Object") != -1:
        ignoreNode = False
        n = Node()
        name = cleanBP(lFind("Name"))
        n.Name = name
        type = lFind3("Class")
        if type == "/Script/BlueprintGraph.K2Node_Tunnel":
            n.type = Tunnel
        elif type == "/Script/BlueprintGraph.K2Node_FunctionEntry":
            n.type = FunctionEntry
        elif type == "/Script/BlueprintGraph.K2Node_VariableGet":
            n.type = VariableGet
        elif type == "/Script/BlueprintGraph.K2Node_VariableSet":
            n.type = VariableSet
        elif type == "/Script/BlueprintGraph.K2Node_CallFunction":
            n.type = Function
        elif type == "/Script/BlueprintGraph.K2Node_CallMaterialParameterCollectionFunction":
            n.type = Function
        elif type == "/Script/BlueprintGraph.K2Node_MacroInstance":
            n.type = Macro
        elif type == "/Script/BlueprintGraph.K2Node_CallArrayFunction":
            n.type = ArrayFunction
            arrayFunctionType = lFind("MemberName", lines[inc]) #Check the next line
            if arrayFunctionType == "\"Array_Set\")":
                n.arrayFunctionType = ArraySet
            else:
                error("Unknown array function type! " + arrayFunctionType)

        elif type == "/Script/BlueprintGraph.K2Node_GetArrayItem":
            n.type = GetArrayItem
        elif type == "/Script/BlueprintGraph.K2Node_DynamicCast":
            n.type = Cast
        elif type == "/Script/BlueprintGraph.K2Node_IfThenElse":
            n.type = IfThen
        elif type == "/Script/BlueprintGraph.K2Node_ExecutionSequence":
            n.type = Sequence
        elif type == "/Script/BlueprintGraph.K2Node_CommutativeAssociativeBinaryOperator":
            n.type = Math
        elif type == "/Script/BlueprintGraph.K2Node_MakeArray":
            n.type = MakeArray
        elif type == "/Script/BlueprintGraph.K2Node_Knot":
            n.type = Knot
        elif type == "/Script/UnrealEd.EdGraphNode_Comment":
            ignoreNode = True
        elif type == "/Script/BlueprintGraph.K2Node_FunctionResult":
            n.type = FunctionResult
        elif type == "/Script/BlueprintGraph.K2Node_BreakStruct":
            n.type = BreakStruct
        else:
            error("Unknown node type! " + type)
        if not ignoreNode:
            nodes[name] = n
    elif line.find("LocalVariables(") != -1:
        v = Pin()
        v.node = n
        v.PinName = cleanBP(lFind("VarName"))
        category = cleanBP(lFind("PinCategory"))
        v.type = getTypeFromBP(category, "PinSubCategoryObject")
        v.PinId = v.PinName
        v.isExec = False
        if category == "object":
            v.isPointer = True
        elif category == "byte":
            v.Enum = cleanBP(lFind("PinSubCategoryObject").split(".")[1])
        elif category == "class":
            v.isPointer = True
        if line.find("ContainerType") != -1:
            v.ContainerType = lFind("ContainerType")
        if v.ContainerType == "Map":
            category = cleanBP(lFind("TerminalCategory"))
            if line.find("TerminalSubCategoryObject") != -1:
                v.TerminalCategory = getTypeFromBP(category, "TerminalSubCategoryObject")
            else:
                v.TerminalCategory = getTypeFromBP(category, None)
            if category == "object":
                v.isTerminalPointer = True
        getDefaultValue(v)
        v.isInput = False
        v.isOutput = True
        n.LocalVariables.append(v)
    elif line.find("FunctionReference=") != -1:
        if line.find("MemberParent") != -1:
            n.MemberParent = cleanBP(lFind("MemberParent").split(".")[1])
        n.MemberName = cleanFunction(cleanBP(lFind("MemberName")))
        if n.MemberName in memberNameReplacements:
            n.MemberName = memberNameReplacements[n.MemberName]
    elif line.find("VariableReference=") != -1:
        n.MemberName = cleanBP(lFind("MemberName"))
        if n.MemberName in memberNameReplacements:
            n.MemberName = memberNameReplacements[n.MemberName]
    elif line.find("NodeComment=") != -1:
        n.NodeComment = cleanBP(lFind("NodeComment"))
    elif line.find("CustomProperties Pin") != -1:
        p = Pin()
        p.node = n
        p.PinId = lFind("PinId")
        category = cleanBP(lFind("PinType.PinCategory"))
        p.type = getTypeFromBP(category, "PinType.PinSubCategoryObject")
        if category == "exec":
            p.isExec = True
        elif category == "object":
            p.isPointer = True
        elif category == "byte":
            p.Enum = cleanBP(lFind("PinType.PinSubCategoryObject").split(".")[1])
        elif category == "class":
            p.isPointer = True
        p.ContainerType = lFind("PinType.ContainerType")
        if p.ContainerType == "Map":
            category = cleanBP(lFind("TerminalCategory"))
            if line.find("TerminalSubCategoryObject") != -1:
                p.TerminalCategory = getTypeFromBP(category, "TerminalSubCategoryObject")
            else:
                p.TerminalCategory = getTypeFromBP(category, None)
            if category == "object":
                p.isTerminalPointer = True
        p.PinName = cleanBP(lFind("PinName"))
        if p.PinName == "__WorldContext":
            continue #Skip adding this pin
        getDefaultValue(p)
        if line.find("DefaultObject=") != -1:
            p.DefaultObject = "U" + cleanBP(lFind("DefaultObject")).split(".")[1]

        if line.find("Direction=\"EGPD_Output\"") == -1:
            p.isInput = True
        p.isOutput = not p.isInput
        
        if line.find("LinkedTo=") != -1:
            for connection in lFind2("LinkedTo"):
                c = PinConnection()
                c.nodeName = connection.split(" ")[0]
                c.PinId = connection.split(" ")[1]
                p.connections.append(c)
        if line.find("SubPins=") != -1:
            for pin in lFind2("SubPins"):
                c = PinConnection()
                c.nodeName = pin.split(" ")[0]
                c.PinId = pin.split(" ")[1]
                p.SubPinCons.append(c)
        isSubPin = False
        if line.find("ParentPin=") != -1:
            parentId = cleanBP(lFind("ParentPin")).split(" ")[1]
            p.ParentPin = n.getPinFromID(parentId)
            isSubPin = True
        if isSubPin:
            n.subPins.append(p)
        else:
            n.pins.append(p)
    elif line.find("MacroGraphReference=") != -1:
        n.MacroGraph = cleanBP(getDotSeparatedName(lFind("MacroGraph")))
    elif line.find("ResolvedWildcardType=") != -1:
        category = cleanBP(lFind("PinCategory"))
        p.ResolvedWildcardType = getTypeFromBP(category, "PinSubCategoryObject")
    inc += 1

#Resolve subpins connections to pins
for key, node in nodes.items():
    for pin in node.pins:
        for con in pin.SubPinCons:
            pin.SubPins.append(node.getPinFromID(con.PinId))
    for pin in node.subPins:
        for con in pin.SubPinCons:
            pin.SubPins.append(node.getPinFromID(con.PinId))

def fixRotationSubpins(pin : Pin):
    rotationPins = []
    index = node.subPins.index(pin.SubPins[0])
    rotationPins.append(pin.SubPins[1]) #Pitch
    rotationPins.append(pin.SubPins[2]) #Yaw
    rotationPins.append(pin.SubPins[0]) #Roll
    pin.SubPins = rotationPins
    for rotPin in rotationPins:
        if index == -1:
            error("Could not find index for first FRotator subPin!")
        node.subPins.remove(rotPin)
        node.subPins.insert(index, rotPin)
        index += 1

#Swap pins in transforms to match C++ form: FTransform(FRotator, FVector, FVector)
for key, node in nodes.items():
    for index, pin in enumerate(node.pins):
        rotationPins = []
        if pin.type == "FTransform" and pin.hasSubPins():
            transformIndex = -1
            rotPin = pin.SubPins[1]
            pin.SubPins[1] = pin.SubPins[0]
            pin.SubPins[0] = rotPin
            for index2, subPin in enumerate(pin.SubPins):
                if subPin.PinName.find("Rotation") != -1:
                    added = True
                    if transformIndex == -1:
                        transformIndex = node.subPins.index(subPin)
                    rotationPins.append(subPin)
                    if subPin.hasSubPins():
                        rotationPins.append(subPin.SubPins[0]) #Roll
                        rotationPins.append(subPin.SubPins[1]) #Pitch
                        rotationPins.append(subPin.SubPins[2]) #Yaw
            for rotPin in rotationPins:
                if transformIndex == -1:
                    error("Could not find index for first transform subPin!")
                node.subPins.remove(rotPin)
                node.subPins.insert(transformIndex - 1, rotPin)
                transformIndex += 1
        if pin.type == "FRotator" and pin.hasSubPins():
            fixRotationSubpins(pin)
    for index, pin in enumerate(node.subPins):
        if pin.type == "FRotator" and pin.hasSubPins():
            fixRotationSubpins(pin)
    
#Untangle all knots (Reroute pins)
for key, node in nodes.items():
    for pin in node.pins:
        if len(pin.connections) > 0:
            for idx, con in enumerate(pin.connections):
                node = getNode(con)
                if node.type == Knot:
                    pin.connections[idx] = resolveKnot(con, pin.isInput)
    for pin in node.subPins:
        if len(pin.connections) > 0:
            for idx, con in enumerate(pin.connections):
                node = getNode(con)
                if node.type == Knot:
                    pin.connections[idx] = resolveKnot(con, pin.isInput)

# branches = {} #node.Name_pin.PinId -> branch name
# branchesAdded = {} #Set of node.Name_pin.PinId
#Add branches for multi connected input execs
multiNodeWarningAdded = False
for key, node in nodes.items():
    if not node.NodeComment.find("cpp:ignore") != -1:
        for pin in node.pins:
            if pin.isInput and pin.isExec and len(pin.connections) > 1:
                error("Multiple input execs entering a node is not allowed! " + node.Name + "|" + node.MemberName + "|" + node.NodeComment + "\nTry using multiple macro instances or sequences instead")
            if node.type != Knot and not (node.type == VariableGet and node.selfIsContext()) and not node.type == Tunnel and not node.hasInputExec() and pin.isOutput and pin.numUniqueNodeConnections() > 1 and node.NodeComment.find("cpp:cache") == -1:
                if not multiNodeWarningAdded:
                    print("Warning! There are pure node(s) that are connected to multiple nodes, this may cause incorrect behavior since this value will be cached in a variable.")
                    print("Try duplicating the node or add cpp:cache as a comment to the node.")
                    multiNodeWarningAdded = True
                if node.type == GetArrayItem:
                    connectedNode = getNode(node.getPin("Array").con())
                    print(node.Name + " | " + connectedNode.MemberName)
                elif node.type == Macro:
                    print(node.MacroGraph + " | " + node.MemberName + "->" + pin.PinName)
                else:
                    print(node.Name + " | " + node.MemberName + "->" + pin.PinName)
                # p = PinConnection()
                # p.nodeName = node.Name
                # p.PinId = pin.PinId
                # if not getBranch(p):
                #     addBranch(p)
                # break

#Find start node
for key, val in nodes.items():
    if not val.hasInputExec() and val.hasOutputExec():
        startNode = val

#Check if this is a macro without execs, just evaluate outputs
if startNode == None:
    for key, node in nodes.items():
        if node.type == Tunnel and node.Name == "K2Node_Tunnel_0":
            startNode = node
        if node.type == Tunnel and node.Name == "K2Node_Tunnel_1":
            endNode = node
    if startNode == None or endNode == None:
        error("Start/End node not found!")
    #Create an exec pin to connect the two nodes
    c = PinConnection()
    c.PinId = "EndNode"
    c.nodeName = "K2Node_Tunnel_1"
    p = Pin()
    p.PinId = "StartNode"
    p.isExec = True
    p.isInput = False
    p.isOutput = True
    p.connections = [c]
    p.type = "exec"
    p.PinName = "StartNode"
    p.node = startNode
    startNode.pins.append(p)

    c = PinConnection()
    c.PinId = "StartNode"
    c.nodeName = "K2Node_Tunnel_0"
    p = Pin()
    p.PinId = "EndNode"
    p.isExec = True
    p.isInput = True
    p.isOutput = False
    p.connections = [c]
    p.type = "exec"
    p.PinName = "EndNode"
    p.node = endNode
    endNode.pins.append(p)

stack = [startNode]
connectionStack = [None]
endvar = "end" + getVarInc()

while len(stack) > 0:
    current : Node = stack.pop()
    currentConnection : PinConnection = connectionStack.pop()
    if current.NodeComment.find("cpp:ignore") != -1:
        continue
    # if currentConnection: #Can be None from unindents and startNode
    #     branch = getBranch(currentConnection)
    #     if branch:
    #         if getBranchNodeAdded(currentConnection):
    #             if not currentConnection.gotoAdded:
    #                 currentConnection.gotoAdded = True
    #                 addCPP(tabs() + "goto " + getBranch(currentConnection) + ";\n", "Add goto")
    #             continue
    #         else:
    #             addBranchNodeAdded(currentConnection)
    #             addCPP(tabs() + branch + ":\n", "Add branch label")

    if current.prefixCode != "":
        addCPP(current.prefixCode, "Add prefix code")
        if current.prefixCode.find("{\n") != -1:
            addTab()

    #First node that starts a BP Macro
    if current == startNode and (current.type == Tunnel or current.type == FunctionEntry):
        if current.MemberName != "":
            functionName = current.MemberName
        if startNode.NodeComment != "":
            functionName = startNode.NodeComment.split("\n")[0]

        returnPins = []
        if current.type == FunctionEntry:
            for key, node in nodes.items():
                if node.type == FunctionResult:
                    for pin in node.pins:
                        if not pin.isExec:
                            returnPins.append(pin)
                    break

        if endNode:
            for pin in endNode.pins:
                if pin.isInput and not pin.isExec:
                    returnPins.append(pin)

        #Function declaration
        line = tabs() + "void " + className + "::" + functionName + "("
        suffix = ""
        for pin in current.pins:
            if pin.isOutput and not pin.isExec:
                suffix += addOutPinToVariable(pin, [], cleanVar(pin.PinName))
                if pin.isPointer:
                    line += typ(pin) + cleanVar(pin.PinName) + ", "
                else:
                    line += "const " + typ(pin) + "& " + cleanVar(pin.PinName) + ", "
        for pin in returnPins:
            if pin.isPointer:
                line += typ(pin) + cleanVar(pin.PinName) + ", "
            else:
                line += typ(pin) + "& " + cleanVar(pin.PinName) + ", "
        line = noComma(line) + ") {\n"
        addTab()

        #Add local variable declarations
        if current.type == FunctionEntry:
            for pin in current.LocalVariables:
                value = ["", pin.DefaultValue]
                suffix += addOutPinToVariable(pin, value, cleanVar(pin.PinName))
                line += tabs() + typ(pin) + cleanVar(pin.PinName) + " = " + pin.DefaultValue + ";\n"

        addCPP(line + suffix, "Add function declaration")
        out = current.getThenOutput()
        if out:
            addUnindentToStack() #Add } to very end of code
            addNodeToStack(out.con())
        else:
            print("Could not find execute pin for start node! " + current.Name)
    elif current.type == Unindent:
        removeTab()
        line = tabs() + "} " + current.postCode + "\n" #Post code may contain a skipping label
        addCPP(line, "Add unindent")
        if line.find("{\n") != -1:
            addTab()
    elif current.type == VariableSet:
        #Resolve variable owner
        selfPin = current.getSelfInput()
        owner = ""
        line = ""
        if selfPin:
            line += resolveReferences(selfPin)
            owner = getInPinToVariable(selfPin) + "->"
        setPin = current.variableSetPin()
            
        #Resolve value for setting
        if current.selfIsContext():
            owner = ""
        if current.NodeComment.find("cpp:local") != -1:
            owner = typ(setPin)
        for pin in current.pins:
            if pin.isInput and not pin.isExec and pin.connected():
                line += resolveReferences(pin)
        
        if setPin.connected():
            line += resolveReferences(setPin)
            val = getInPinToVariable(setPin)
            line += tabs() + owner + cleanVar(setPin.PinName) + " = " + val + ";\n"
        else:
            val = setPin.DefaultValue
            if setPin.type != "FName" and setPin.type != "FString" and setPin.type != "FText" and setPin.DefaultValue == "":
                val = "nullptr"
            line += tabs() + owner + cleanVar(setPin.PinName) + " = " + val + ";\n"
        addCPP(line, "Add variable set")
        out = current.getThenOutput()
        if out:
            addNodeToStack(out.con())
    elif current.type == Function:
        line = getFunctionCode(current)
        addCPP(line, "Add function call")
        out = current.getThenOutput()
        if out:
            addNodeToStack(out.con())
    elif current.type == Macro:
        if current.MacroGraph == "StandardMacros:ForEachLoop":
            usesIndex = False
            usesElement = False
            indexPin : Pin = None
            elementPin : Pin = None
            arrayPin : Pin = None
            loopBodyPin : Pin = None
            completedPin : Pin = None
            for pin in current.pins:
                if pin.PinName == "Array Index" and pin.connected():
                    usesIndex = True
                    indexPin = pin
                elif pin.PinName == "Array Element" and pin.connected():
                    usesElement = True
                    elementPin = pin
                elif pin.PinName == "Array" and pin.isInput:
                    arrayPin = pin
                elif pin.PinName == "LoopBody" and pin.isOutput:
                    loopBodyPin = pin
                elif pin.PinName == "Completed" and pin.isOutput:
                    completedPin = pin
                
            line = resolveReferences(arrayPin)
            suffix = ""
            arrayVar = getInPinToVariable(arrayPin)

            if usesIndex and usesElement:
                ivar = "i" + getVarInc()
                suffix += addOutPinToVariable(indexPin, [], ivar)
                line += tabs() + "for(int " + ivar + " = 0; " + ivar + " < " + arrayVar + ".Num(); ++" + ivar + ") {\n"
                addTab()
                value = [arrayVar, "[", ivar, "]"]
                suffix += addOutPinToVariable(elementPin, value)
                line += tabs() + typ(elementPin) + getOutPinToVariable(elementPin) + " = " + arrayToStr(value) + ";\n"
            elif usesIndex:
                ivar = "i" + getVarInc()
                
                suffix += addOutPinToVariable(indexPin, [], ivar)
                line += tabs() + "for(int " + ivar + " = 0; " + ivar + " < " + arrayVar + ".Num(); ++" + ivar + ") {\n"
                addTab()
            elif usesElement:
                suffix += addOutPinToVariable(elementPin, [])
                line += tabs() + "for(auto& " + getOutPinToVariable(elementPin) + " : " + arrayVar + ") {\n"
                addTab()
            addCPP(line + suffix, "Add for each loop macro")
            if completedPin.connected():
                addNodeToStack(completedPin.con())
            addUnindentToStack()
            if loopBodyPin.connected():
                addNodeToStack(loopBodyPin.con())
        elif current.MacroGraph == "StandardMacros:IsValid":
            addCPP(addTwoPinBranch(current), "Add isValid macro")
        elif current.MacroGraph == "StandardMacros:ForLoopWithBreak":
            if currentConnection.PinId == current.getPin("Break").PinId:
                addCPP(tabs() + getBreak(current) + " = false;\n", "Add for loop with break macro | Break pin")
            else:
                firstPin = current.getPin("FirstIndex")
                lastPin = current.getPin("LastIndex")
                indexPin = current.getPin("Index")
                line = ""
                suffix = ""
                line += resolveReferences(firstPin)
                line += resolveReferences(lastPin)
                breakVar = addBreak(current)
                ivar = "i" + getVarInc()
                
                suffix += addOutPinToVariable(indexPin, [], ivar)
                line += tabs() + "bool " + breakVar + " = true;\n"
                line += tabs() + "for(int " + ivar + " = " + getInPinToVariable(firstPin) + "; " + ivar + " <= " + getInPinToVariable(lastPin) + " && " + breakVar + "; ++" + ivar + ") {\n"
                addTab()
                bodyPin = current.getPin("LoopBody")
                completedPin = current.getPin("Completed")
                if completedPin.connected():
                    addNodeToStack(completedPin.con())
                addUnindentToStack()
                if bodyPin.connected():
                    addNodeToStack(bodyPin.con())
                addCPP(line + suffix, "Add for loop with break macro | Other pins")
        # elif current.MacroGraph in EasyMacroCalls:
        else:
            addCPP(easyMacroCall(current), "Easy macro call")
        # else:
            # error("Macro not yet implemented! " + current.Name + " | " + current.MacroGraph)
    elif current.type == ArrayFunction:
        line = ""
        if current.arrayFunctionType == ArraySet:
            arrayPin = None
            indexPin = None
            itemPin = None
            for pin in current.pins:
                line += resolveReferences(pin)
                if pin.PinName == "TargetArray":
                    arrayPin = pin
                if pin.PinName == "Index":
                    indexPin = pin
                if pin.PinName == "Item":
                    itemPin = pin
            if arrayPin == None or indexPin == None or itemPin == None:
                error("Array/Index/Item Pin not found! " + current.Name)
            line += tabs() + getInPinToVariable(arrayPin) + "[" + getInPinToVariable(indexPin) + "] = " + getInPinToVariable(itemPin) + ";\n"
            addCPP(line, "Add array set function")
        out = current.getThenOutput()
        if out:
            addNodeToStack(out.con())
    elif current.type == Cast:
        addCPP(addTwoPinBranch(current), "Add cast")
    elif current.type == IfThen:
        addCPP(addTwoPinBranch(current), "Add ifthen")
    elif current.type == Sequence:
        #This sequence check is unnecessary now that branches are removed
        # sequenceVar = "sequence" + getVarInc() #Used to handle other outside execution pins entering a node thats connected to this sequence, generates a bool that doesn't allow that execution line to continue through to other sequence pins
        # line = tabs() + "int " + sequenceVar + " = 0;\n"
        inc = 0
        for pin in current.pins:
            if pin.isOutput and pin.connected():
                inc += 1
        for pin in reversed(current.pins):
            if pin.isOutput and pin.connected():
                inc -= 1
                # addUnindentToStack()
                # addNodeToStack(pin.con(), tabs() + "if(" + sequenceVar + " == " + str(inc) + ") {\n\t" + tabs() + "++" + sequenceVar + ";\n")
                addNodeToStack(pin.con())
        # addCPP(line, "Add sequence")
    elif current.type == Tunnel: #Output tunnel
        line = ""
        for pin in current.pins:
            if pin.isInput and not pin.isExec:
                line += resolveReferences(pin)

        for pin in current.pins:
            if pin.isInput and not pin.isExec:
                line += tabs() + cleanVar(pin.PinName) + " = " + getInPinToVariable(pin) + ";\n"
        addCPP(line, "Add tunnel")
    elif current.type == FunctionResult:
        line = ""
        for pin in current.pins:
            if not pin.isExec:
                line += resolveReferences(pin)
        for pin in current.pins:
            if not pin.isExec:
                line += tabs() + cleanVar(pin.PinName) + " = " + getInPinToVariable(pin) + ";\n"
        addCPP(line, "Add function result")
    else:
        error("Unhandled node type for stack traversal! " + str(current.type))

removedVars = []

def nearbyMath(value : List[str], index):
    return False
    before = index - 1
    after = index + 1
    if before >= 0:
        for math in mathSymbols:
            if value[before] == math:
                return True
    if after < len(value):
        for math in mathSymbols:
            if value[after] == math:
                return True
    return False

def resolveFlattenedVar(var : str) -> str:
    if var in vars:
        value = vars[var]
        result = ""
        for i in range(len(value)):
            if i % 2 == 0: #variable name
                if value[i] in removedVars:
                    if nearbyMath(value, i):
                        result += "(" + resolveFlattenedVar(value[i]) + ")"
                    else:
                        result += resolveFlattenedVar(value[i])
                else:
                    if nearbyMath(value, i):
                        result += "(" + value[i] + ")"
                    else:
                        result += value[i]
            else: #operator
                result += value[i]
        return result
    return var

def removeDeclaration(var):
    global cpp
    index = cpp.find(var + " = ")
    if index == -1:
        error("Attempted to remove non existent declaration! " + var)
    start = index
    while start > 0 and cpp[start] != "\n":
        start -= 1
    end = index
    while end < len(cpp) - 1 and cpp[end] != "\n":
        end += 1
    cpp = cpp[:start] + cpp[end:]

def findDoubles(var):
    reg = r"[^\w\d](" + var + r")[^\w\d]"
    matches = re.findall(reg, cpp)
    if len(matches) == 2:
        removedVars.append(var)
                   
if flattenCode:
    for var, value in vars.items():
        findDoubles(var)

    for var in reversed(removedVars):
        removeDeclaration(var)

    for var in reversed(removedVars):
        if cpp.find(var) != -1:
            reg = r"([^\w\d])" + var + r"([^\w\d])"
            replacement = resolveFlattenedVar(var)
            cpp = re.sub(reg, r"\1" + replacement + r"\2", cpp)
    
for key in postReplacements:
    cpp = cpp.replace(key, postReplacements[key])

for key, value in postRegexReplacements.items():
    cpp = re.sub(key, value, cpp)

f = open("output.cpp", "w")
f.write(cpp)
f.close()

pyperclip.copy(cpp)
print("Output copied to clipboard")
print("Output written to:")
print(str(pathlib.Path().absolute()) + "\\output.cpp")

k2Index = cpp.lower().find("k2")
if k2Index != -1:
    print("K2 found! " + cpp[k2Index : k2Index + 40 ])

writeToPersistent("currentVarInc=" + str(currentVarInc))

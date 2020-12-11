import copy
import os
import numpy as np
import pandas as pd
import pickle
import sys

def make_dict(sheetName, varName, multiple=False):
    if not os.path.exists(fnExcel):
        raise "Cannot find %s"%fnExcel
    out1 = pd.read_excel(fnExcel, sheet_name=sheetName, engine="openpyxl")
    df = out1.dropna(axis=1, how="all")
    if multiple:
        final_dict = {Id: group for Id, group in df.groupby(varName)}
        return final_dict, {'dict_key': varName, 'dict_columns': None}
    else:
        df_aux = df.loc[:, df.columns != varName]
        id_list = df[varName].values.tolist()
        attribute_list = df_aux.values.tolist()
        final_dict = dict(zip(id_list, attribute_list))
        dict_names = [n for n in df_aux][0:]
        return final_dict, {'dict_key': varName, 'dict_columns': dict_names}

def bidirectional_relations(edge_type_dict):
    list_bidirectional_relations = []
    for idEdge in edge_type_dict.keys():
        edge = edge_type_dict[idEdge]
        edge_name = edge[3]
        bidirectional = " is related to " in edge_name or \
                        " is similar to " in edge_name or \
                        " is also " in edge_name or \
                        " is seen with " in edge_name or \
                        " can be seen also with " in edge_name
        if bidirectional:
            list_bidirectional_relations.append(idEdge)
    return list_bidirectional_relations
            
def load_database(fn):
    infile = open(fn,'rb')
    (lang_dict, lang_dict_info, entity_type_dict, entity_type_dict_info, 
     entity_dict, entity_dict_info,
     edge_type_dict, edge_type_dict_info, list_bidirectional_relations,
     edge_dict, edge_dict_info, details_dict, details_dict_info,
     resources_dict, resources_dict_info) = \
       pickle.load(infile)
    infile.close()
    return (lang_dict, lang_dict_info, entity_type_dict, entity_type_dict_info, 
            entity_dict, entity_dict_info,
            edge_type_dict, edge_type_dict_info, list_bidirectional_relations,
            edge_dict, edge_dict_info, details_dict, details_dict_info,
            resources_dict, resources_dict_info)

def separate_entities_by_type(entity_type_dict, entity_dict):
    entities = {}
    for idEntity in entity_dict:
        idEntityType = entity_dict[idEntity][1]
        if idEntityType not in entities:
            entities[idEntityType]=[]
        entities[idEntityType].append(idEntity)
    return entities

def count_edges(edge_dict):
    entities_count = {}
    for idEdge in edge_dict:
        idEntity1 = edge_dict[idEdge][0]
        idEntity2 = edge_dict[idEdge][1]
        if not idEntity1 in entities_count:
            entities_count[idEntity1] = [0,0,0] # Outgoing, incoming
        if not idEntity2 in entities_count:
            entities_count[idEntity2] = [0,0,0]
        entities_count[idEntity1][0]+=1
        entities_count[idEntity2][1]+=1
    for idEntity in entities_count:
        entities_count[idEntity][2]=entities_count[idEntity][0]+entities_count[idEntity][1]
    return entities_count

def report_edge_mistakes(edge_dict, edge_type_dict, entity_dict):
    for keyEdge in edge_dict:
        edge = edge_dict[keyEdge]
        edgeType = edge[2]
        edgeType1 = edge_type_dict[edgeType][0]
        edgeType2 = edge_type_dict[edgeType][1]

        idEntity1 = edge[0]
        idEntity2 = edge[1]
        entityType1 = entity_dict[idEntity1][1]
        entityType2 = entity_dict[idEntity2][1]
        if entityType1!=edgeType1 and entityType2!=edgeType2:
            print("%s (%d) -> %s (%d) [%s]"%(entity_dict[idEntity1][0],
                                             idEntity1,
                                             entity_dict[idEntity2][0],
                                             idEntity2,
                                             edge[3]))

def add_directional_edges(edge_dict, list_bidirectional_relations):
    edges_present = {}
    for keyEdge in edge_dict:
        edge = edge_dict[keyEdge]
        edgeType = edge[2]

        if edgeType in list_bidirectional_relations:
            idEntity1 = edge[0]
            idEntity2 = edge[1]
            edges_present[(idEntity1,idEntity2,edgeType)] = 1

    toAdd = []
    for keyEdge in edge_dict:
        edge = edge_dict[keyEdge]
        edgeType = edge[2]

        if edgeType in list_bidirectional_relations:
            idEntity1 = edge[0]
            idEntity2 = edge[1]
            if idEntity1!=idEntity2 and \
               not (idEntity2,idEntity1,edgeType) in edges_present:
                toAdd.append([idEntity2,idEntity1,edgeType,edge[3],
                                      edge[4],edge[5]])

    nextKey = np.max([key for key in edge_dict])+1
    N=0
    for edge in toAdd:
        edge_dict[nextKey]=edge
        nextKey+=1
        N+=1
    print("%d new edges added"%N)

class Node():
    def __init__(self, idEntity, idEntityType, entityName, id_dict):
        self.idEntity = idEntity
        self.idEntityType = idEntityType
        self.entityName = entityName
        self.incomingEdges = {}
        self.outgoingEdges = {}
        self.reachableDown = {}
        self.reachableUp = {}
    
    def addOutgoingEdge(self, idEntityTo, idEdgeType, strength):
        edgeKey = (idEntityTo, idEdgeType)
        if not edgeKey in self.outgoingEdges:
            self.outgoingEdges[edgeKey] = 0.0
        self.outgoingEdges[edgeKey] += strength

    def addIncomingEdge(self, idEntityFrom, idEdgeType, strength):
        edgeKey = (idEntityFrom, idEdgeType)
        if not edgeKey in self.incomingEdges:
            self.incomingEdges[edgeKey] = 0.0
        self.incomingEdges[edgeKey] += strength
    
    def createPathsDown(self, distance, graph, weight, threshold):
        if distance==0 and weight>threshold:
            return [Path(self.idEntity, weight)]
        
        paths = []
        for idEntityTo, idEdgeType in self.outgoingEdges:
            strength = self.outgoingEdges[(idEntityTo, idEdgeType)]
            weightStrength = weight*strength
            if weightStrength>threshold:
                pathsTo = graph[idEntityTo].createPathsDown(distance-1, graph,
                                                            weightStrength,
                                                            threshold)
                for path in pathsTo:
                    path.prependNode(self.idEntity, weight, idEdgeType,
                                     strength)
                    if path.originEntity!=path.terminalEntity:
                        paths.append(path)
        
        return paths

    def createPaths(self, distance, graph, threshold=0.25):
        for d in range(1,distance+1):
            paths = self.createPathsDown(d, graph, 1, threshold)
            for path in paths:
                if not path.terminalEntity in self.reachableDown:
                    self.reachableDown[path.terminalEntity] = []
                self.reachableDown[path.terminalEntity].append(copy.copy(path))

class Path():
    def __init__(self, idEntity=None, weight=1):
        self.path = []
        self.originEntity = None
        self.terminalEntity = None
        if idEntity is not None:
            self.originEntity = idEntity
            self.addTerminalNode(idEntity, weight)
    
    def addTerminalNode(self, idEntity, weight):
        self.path.append((weight, None, None, None))
        self.terminalEntity = idEntity

    def prependNode(self, idEntity, weight, idEdgeType, edgeStrength):
        self.path.insert(0,(weight, self.originEntity, idEdgeType, edgeStrength))
        self.originEntity = idEntity
    
    def appendNode(self, idEntity, weight, idEdgeType, edgeStrength):
        self.path.append((weight, idEntity, idEdgeType, edgeStrength))
        self.terminalEntity = idEntity
    
    def getLastWeight(self):
        if len(self.path)==0:
            return None, 0.0
        else:
            return self.terminalEntity, self.path[-1][0]
    
    def __str__(self):
        retval = "%d --> %d: [%d"%(self.originEntity, self.terminalEntity,
                                   self.originEntity)
        for weight, idEntity, idEdgeType, edgeStrength in self.path:
            retval += " (w=%f)"%weight
            if idEntity is not None:
                retval+=" --(%d,%f)--> %d"%(idEdgeType, edgeStrength, idEntity)
        retval+="]"
        return retval

    def pretty(self, entity_dict, edge_type_dict):
        strOrigin = entity_dict[self.originEntity][0]
        strTerminal = entity_dict[self.terminalEntity][0]
        retval = "%s (%d) --> %s (%d): [%s (%d)"%(strOrigin,
                                                  self.originEntity, 
                                                  strTerminal,
                                                  self.terminalEntity,
                                                  strOrigin,
                                                  self.originEntity)
        for weight, idEntity, idEdgeType, edgeStrength in self.path:
            retval += " (w=%f)"%weight
            if idEntity is not None:
                retval+=" --(%s (%d),%f)--> %s (%d)"%\
                    (edge_type_dict[idEdgeType][3], idEdgeType,
                     edgeStrength, entity_dict[idEntity][0], idEntity)
        retval+="]"
        return retval
          

class Graph():
    def __init__(self, entity_dict, entity_type_dict, edge_dict, id_dict):
        self.graph = {}
        self.id_dict = id_dict
        self.node_max = 0
        
        # Create all nodes
        for idEntity in entity_dict:
            self.graph[idEntity]=Node(idEntity, entity_dict[idEntity][1], 
                                      entity_dict[idEntity][0], id_dict)
            self.node_max = max(self.node_max, idEntity)
        
        # Create all edges
        for idEdge in edge_dict:
            edge = edge_dict[idEdge]
            idEntityFrom = edge[0]
            idEntityTo = edge[1]
            idEdgeType = edge[2]
            strength = edge[5]
            
            self.graph[idEntityFrom].addOutgoingEdge(idEntityTo, idEdgeType,
                                                     strength)
            self.graph[idEntityTo].addIncomingEdge(idEntityFrom, idEdgeType,
                                                   strength)
    
    def createPaths(self, distance=2, threshold=0.25):
        for idEntity in self.graph:
            self.graph[idEntity].createPaths(distance, self.graph, threshold)
            for idEntityReachable in self.graph[idEntity].reachableDown:
                entityReachable = self.graph[idEntityReachable]
                for path in self.graph[idEntity].reachableDown[idEntityReachable]:
                    if not idEntity in entityReachable.reachableUp:
                        entityReachable.reachableUp[idEntity] = []
                    entityReachable.reachableUp[idEntity].append(path)
    
    def getNodeMax(self):
        return self.node_max
    
    def getNode(self, idEntity):
        return self.graph[idEntity]


if __name__=="__main__":
    if len(sys.argv) <= 1:
        print("Usage: python3 copenmed_tools excel2pkl <excelfile>")
        print("   <excelfile> must contain the Excel sheets of COpenMed")
        print("Usage: python3 copenmed_tools check <pklfile>")
        print("   <pklfile> must be produced by excel2pkl")
        sys.exit(1)
    
    if sys.argv[1]=="excel2pkl":
        fnExcel = sys.argv[2]
        
        # Read all sheets
        lang_dict, lang_dict_info               = make_dict('idiomas',          'IdIdioma')
        entity_type_dict, entity_type_dict_info = make_dict('tipos_entidad',    'IdTipoEntidad')
        entity_dict, entity_dict_info           = make_dict('entidades',        'IdEntidad')
        edge_type_dict, edge_type_dict_info     = make_dict('tipos_relaciones', 'IdTipoAsociacion')
        edge_dict, edge_dict_info               = make_dict('relaciones',       'IdAsociacion')
        
        # Details and resources have several entries per idEntity
        details_dict, details_dict_info         = make_dict('detalles', 'IdEntidad', True)
        resources_dict, resources_dict_info     = make_dict('recursos', 'IdEntidad', True)
        
        list_bidirectional_relations = bidirectional_relations(edge_type_dict)
        
        # Pickle file
        filename = 'copenmed.pkl'
        outfile = open(filename,'wb')
        obj = (lang_dict, lang_dict_info, entity_type_dict, entity_type_dict_info, 
               entity_dict, entity_dict_info,
               edge_type_dict, edge_type_dict_info, list_bidirectional_relations,
               edge_dict, edge_dict_info, details_dict, details_dict_info,
        	   resources_dict, resources_dict_info)
        pickle.dump(obj,outfile)
        outfile.close()
        
    elif sys.argv[1]=="check":
        fnPickle = sys.argv[2]
        lang_dict, lang_dict_info, entity_type_dict, entity_type_dict_info,\
        entity_dict, entity_dict_info, edge_type_dict, edge_type_dict_info, \
        list_bidirectional_relations, \
        edge_dict, edge_dict_info, details_dict, details_dict_info, \
        resources_dict, resources_dict_info = \
        load_database(fnPickle)
    
        report_edge_mistakes(edge_dict, edge_type_dict, entity_dict)


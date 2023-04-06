# Importing dependencies
from platform import node
import pygsheets
import pandas
import os,datetime
from py2neo import Graph
from py2neo.ogm import Repository, Model, Property, RelatedTo, Label
from py2neo.matching import *
import re,json

#Import pyxlrd

#Read configs from file in path "goatconfigs"


# GOAT Definitions
def get_rels_from_file(relfile):
    adddate=relfile.split("/")[-1].replace("relationships-","")
    with open(relfile) as f:
        rels=f.read().split("\n")
        if "" in rels:
            rels.remove("")
        relationships=[{"source":rel.split("|")[0],"story":rel.split("|")[1],"target":rel.split("|")[2],"date":"29-May-2022"} for rel in rels]
    return relationships
# function to get a mojogoat configuration for a specific dbname
def get_mgc(dbname="neo4j", goatconfigpath="/xpal-data/goatconfigs/neo4jgoatconfig.json"):
    with open(goatconfigpath) as f:
        goatconfig=json.loads(f.read())
    goatconfig['dbname']=dbname
    return goatconfig

# function to generate a nodeid
def get_nodeid(node):
    nodeid=node.replace(" ","")
    nodeid=re.sub('[^A-Za-z0-9]+', '', nodeid).lower()
    return nodeid


# Defining the types of nodes we are tracking
class Node(Model):
    __primarykey__="nodeid"
    nodeid = Property()
    name = Property()
    linkedto=RelatedTo("Node")
    isthesameas=RelatedTo("Node")
    nodetype = Property()

    def get_properties(self):
        return {
            'nodeid': self.nodeid,
            'name': self.name,
            'nodetype': self.nodetype
        }
    def set_properties(self,nodedict):
        if "name" in nodedict.keys():
            self.name=nodedict['name']
        return {
            'nodeid': self.nodeid,
            'name': self.name,
            'nodetype': self.nodetype
        }
    def __repr__(self):
        return "Node(nodeid={}, name={})".format(
            self.nodeid, self.name
        )

# These classes are only relevant for having more properties in the Neo4J daabase itself. Not strictly relevant methinks: Arjun 2023-04-06
# define a class to store Person records with properties nodeid, name, linkedto, urls
class Person(Node):
    __primarykey__="nodeid"
    nodeid = Property()
    name = Property()
    role=Property()
    linkedto=RelatedTo(Node)
    urls=Property()
    organization=Property()
    isthesameas=RelatedTo(Node)
    def get_properties(self):
        return {
            "nodeid": self.nodeid,
            "name": self.name,
            "role": self.role,
            "urls": self.urls,
            "organization": self.organization
        }
    
    
# define a class to store Organizations with properties nodeid, name, linkedto
class Organization(Node):
    __primarykey__="nodeid"
    nodeid = Property()
    name = Property()
    linkedto=RelatedTo(Node)    
    description=Property()
    founded=Property()
    hq=Property()
    isthesameas=RelatedTo("Node")
    
    def get_properties(self):
        return {
            "nodeid": self.nodeid,
            "name": self.name,
            "description": self.description,
            "founded": self.founded,
            "hq": self.hq
        }
    
# define a class to store Artefacs with properties name, type, summary, and url
class Artefact(Node):
    __primarykey__="nodeid"
    nodeid = Property()
    name = Property()
    atype=Property()
    summary=Property()
    url=Property()
    linkedto=RelatedTo(Node)
    isthesameas=RelatedTo("Node")
 
    def get_properties(self):
        return {
            "nodeid": self.nodeid,
            "name": self.name,
            "atype": self.atype,
            "summary": self.summary,
            "url": self.url
        }


# Define a class for a MojoGOAT
class Neo4jGoat:
    def __init__(self,goatconfig):
        self.graph = Graph("bolt://"+goatconfig['dburl'], auth=(goatconfig['username'], goatconfig['password']), name=goatconfig['dbname'])
        self.repo = Repository("bolt://" + goatconfig['username'] + "@" +goatconfig['dburl'], password=goatconfig['password'], name=goatconfig['dbname'])
        self.nodes=NodeMatcher(self.graph)
        self.dbname=goatconfig['dbname']

    # Self Reporting

    #function to get the graph composition
    def get_compostion(self):
        return[{label:self.nodes.match(label).count()}for label in list(self.graph.schema.node_labels)]
        
    # function to add a generic node to the graph
    def add_node(self,**kwargs):
        nodeid=kwargs['nodeid']
        print(nodeid)
        enode=self.repo.match(Node,nodeid).first()
        if enode is not None:
            print("Node exists")
            enode.set_properties(kwargs)
            self.repo.save(enode)
            return enode
        print("Adding new node")
        p=Node(**kwargs)
        self.repo.save(p)
        return p
    
    # function to update the labels of a node
    def update_labels(self,nodeid,labels):
        thisnode=self.nodes.match("Node",nodeid=nodeid).first()
        tx=self.graph.begin()
        thisnode.update_labels(labels)
        tx.push(thisnode)
        self.graph.commit(tx)
        return thisnode.labels
    
    def get_labels(self,nodeid):
        thisnode=self.nodes.match("Node",nodeid=nodeid).first()
        return thisnode.labels

    # function to get the relationship between two nodes
    def get_story(self,node1,node2):
        story=node1.linkedto.get(node2,"story")
        return story

    #function to create and add lines to a relationship -- TODO: add a way to include timestamps for relationship updates
    def link(self,x,y,storyline,adddate):
        curstory=self.get_story(x,y)
        newstory=[storyline]
        print(newstory)
        if curstory is not None:
            newstory=list(set(newstory+curstory))
        output=x.linkedto.add(y, properties={"story":newstory,"adddate":adddate,"updatedate":datetime.datetime.now()})
        return output

    # function to link nodes with relationship storyline "is"
    def link_is(self,node1,node2):
        node1.isthesameas.add(node2)
        node2.isthesameas.add(node1)
        self.repo.save(node1)
        self.repo.save(node2)

    '''
    Obsolete functions
    # function to add an artefact 
    def add_artefact(self,node, url=None, summary=None, atype=None):
        nodeid=get_nodeid(node)
        a=Artefact(nodeid=nodeid, name=node, url=url, summary=summary, atype=type)
        self.repo.save(a)
        return a

    def eat_goat_nodes(self,goat):
        for node in goat.all_nodes():
            self.add_node(**node)
            self.update_labels(node['nodeid'],node['labels'])
    
    def eat_goat_rels(self,goat):
        for rel in goat.all_rels():
            source=self.add_node(nodeid=rel['source'])
            target=self.add_node(nodeid=rel['target'])
            self.link(source,target,rel['story'],rel['date'])
            self.repo.save(source)

    # Functions to get poop and milk out of the GOAT
    '''

    # function to dump all relationships to a file
    def dump_all_rels(self,path="/opt/xpal-data/mojogoat"):
        rellines=""    
        for node in self.repo.match(Node).all():
            for rel in node.linkedto.triples():
                try:
                    for line in rel[1][1]['story']:
                        rellines=rellines+"\n"+"|".join([rel[0].nodeid,line,rel[2].nodeid])
                except Exception as e:
                    print(str(e))
            for rel in node.isthesameas.triples():
                rellines=rellines+"\n"+"|".join([rel[0].nodeid,"is the same as",rel[2].nodeid])
        with open(os.path.join(path,self.dbname+"-"+datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")),"w") as f:
            f.write(rellines)



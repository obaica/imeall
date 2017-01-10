import os
import sys
import json
import glob
import argparse
import numpy as np
from   peewee   import *
from   quippy   import Atoms, set_fortran_indexing
from   datetime import datetime, timedelta
from   models   import GBAnalysis, PotentialParameters



set_fortran_indexing(False)
GRAIN_DATABASE = "/home/lambert/pymodules/imeall/imeall/grain_boundaries/"

try: 
  DATABASE   = os.environ['GBDATABASE']
except KeyError:
  sys.exit("NO SQL GBDATABASE in Environment")

database       = SqliteDatabase(DATABASE)
class BaseModel(Model):
  class Meta():
    database = database

class GrainBoundary(BaseModel):
  """
  Canonical Parent Grain
  Vectors are serialized to csv. We may want to 
  separate this out into tables if heavy searching
  becomes necessary.
  :params: angle misorientation angle in radians.
  """
  gb_type          = CharField()
  boundary_plane   = CharField()
  z_planes         = CharField()
  orientation_axis = CharField()
  n_at             = IntegerField()
  coincident_sites = IntegerField()
  angle            = FloatField()
  height           = FloatField()
  area             = FloatField()
  notes            = TextField(default="")
  path             = CharField()
#Placing a unique constraint on the canonical grain.
  gbid             = CharField(unique=True)

class SubGrainBoundary(BaseModel):
  """
  :path: relative to the grainboundary database root.
  :params: rbt rigid body translations.
  :params: grain_boundary every grain is a subgrain of the GrainBoundary Class.
  """
  canonical_grain = ForeignKeyField(GrainBoundary, "subgrains")
  converged       = BooleanField()
  rbt             = CharField()
  path            = CharField()
  potential       = CharField()
  rcut            = FloatField()
  area            = FloatField()
  n_at            = IntegerField()
  E_gb            = FloatField(default=0.0)
  E_gb_init       = FloatField(default=0.0)
  notes           = TextField(default="")
  gbid            = CharField()
  class Meta:
		indexes=(
     				  (('potential', 'gbid'), True), #trailing comma is necessary
    				)

class Fracture(BaseModel):
  """
  :params:G stress energy release rate.
  :params:strain_rate.
  :params:sim_T simulation temperature.
  """
  fracture_system = CharField()
  G               = FloatField()
  strain_rate     = FloatField()
  sim_T           = FloatField()
  notes           = CharField(default="")

class Dislocation(BaseModel):
  gbid  =  CharField()

def serialize_vector(vector):
  return ','.join(map(str, vector))

def deserialize_vector_float(ser_vec):
  return map(float, ser_vec.split(','))

def deserialize_vector_int(ser_vec):
  return map(int, ser_vec.split(','))

def create_tables(database):
  """
  :method:`create_tables` 
  """
  database.connect()
  database.create_tables([GrainBoundary,SubGrainBoundary], True)

def add_conv_key(material='alphaFe', or_axis='001'):
  analyze  = GBAnalysis()
  gb_files = []
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, os.path.join(material, or_axis))), gb_files, 'gb.json')
  for gb in gb_files:
    print gb[0], gb[1]
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    GB_model = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
    for subgb_model in GB_model.subgrains:
      subgb_dict_path = os.path.join(subgb_model.path,'subgb.json')
      subgb_dict_path = os.path.join(GRAIN_DATABASE, subgb_dict_path)
      with open(subgb_dict_path,'r') as f:
        subgb_dict = json.load(f)
      try:
        print subgb_dict['gbid'], subgb_dict['converged']
      except KeyError:
        print 'Adding Convergence Keys'
        if 'E_gb' in subgb_dict.keys():
          subgb_dict['converged'] = True
        else:
          subgb_dict['converged'] = False
        with open(subgb_dict_path,'w') as f:
          json.dump(subgb_dict, f, indent=2)

def check_dir_integrity(material='alphaFe', or_axis='001'):
  analyze  = GBAnalysis()
  gb_files = []
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, os.path.join(material, or_axis))), gb_files, 'gb.json')
  for gb in gb_files:
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    GB_model = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
    for subgb_model in GB_model.subgrains:
      subgb_dict_path = os.path.join(subgb_model.path,'subgb.json')
      subgb_dict_path = os.path.join(GRAIN_DATABASE, subgb_dict_path)
      try:
        with open(subgb_dict_path,'r') as f:
          subgb_dict = json.load(f)
      except IOError:
        NOINPUT = True
        print subgb_dict_path
        while NOINPUT:
          user_input = raw_input("Directory missing delete model (y/n)?")
          if user_input == 'y':
            print 'Deleting Model'
            subgb_model.delete_instance()
            NOINPUT=False
          elif user_input =='n':
            print 'Keeping Model'
            NOINPUT=False
          else:
            pass

def gb_check_conv(material='alphaFe', or_axis='001', modify_db=False):
  """
  :method:`gb_conv_json_model` scan through grainboundary directory tree,
           inspect the json dictionary and update the SQLite model.
  :attributes:
    test_run: Boolean. If True do not update gb_model in database.
    material: Which material to do convergence integrity on.
    or_axis: Which orientation axis to check.
  """
  analyze  = GBAnalysis()
  gb_files = []
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, os.path.join(material, or_axis))), gb_files, 'gb.json')
  no_struct_file = open('no_struct.txt','a')
  for gb_num, gb in enumerate(gb_files[:]):
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    GB_model = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
    for subgb_model in GB_model.subgrains:
      subgb_dict_path = os.path.join(subgb_model.path,'subgb.json')
      subgb_dict_path = os.path.join(GRAIN_DATABASE, subgb_dict_path)
      with open(subgb_dict_path,'r') as f:
        subgb_dict = json.load(f)
      struct_path = os.path.join(subgb_model.path, subgb_model.gbid+'_traj.xyz')
      struct_path = os.path.join(GRAIN_DATABASE, struct_path)
      try:
        assert subgb_model.converged==subgb_dict['converged']
      except AssertionError:
        if not modify_db:
          print 'Not updating:'
          print subgb_dict_path
          print 'Model: ', subgb_model.converged, 'Json:', subgb_dict['converged']
        else:
          try:
            assert type(subgb_dict['converged'])==bool  
          except:
            print "json 'converged' value not boolean. json file could be corrupted:"
            print subgb_dict_path
          else:
            print 'Updating model instance in database:'
            print subgb_dict_path
            print 'Model: ', subgb_model.converged, 'Json:', subgb_dict['converged']
            subgb_model.converged = subgb_dict['converged']
            subgb_model.save()
      try:
        assert (abs(subgb_model.E_gb - subgb_dict['E_gb']) < 1e-8)
      except AssertionError:
        print 'Model:', subgb_model.E_gb, 'JSON:',  subgb_dict['E_gb'], subgb_model.E_gb-subgb_dict['E_gb']
        print subgb_dict_path
        subgb_model.E_gb = subgb_dict['E_gb']
        subgb_model.save()
      except KeyError:
        print 'No Key'
        print subgb_dict_path
        print subgb_dict['converged']
        subgb_dict['converged']=False
        with open(subgb_dict_path, 'w') as f:
          json.dump(subgb_dict, f, indent=2)

def gb_check_force(material='alphaFe', or_axis='001', force_tol=0.025, modify_db=False):
  """
  :method:`gb_check_force`. Recurse through directory tree, loading the structure file, json dict 
  and the model for each subgrain. Check that the force tolerance in structure file has actually been 
  met for convergence.
  """
  analyze  = GBAnalysis()
  gb_files = []
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, os.path.join(material, or_axis))), gb_files, 'gb.json')
  start = 1
  no_struct_file = open('no_struct.txt','a')
  for gb_num, gb in enumerate(gb_files[start:]):
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    GB_model = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
    for subgb_model in GB_model.subgrains:
      subgb_dict_path = os.path.join(subgb_model.path,'subgb.json')
      subgb_dict_path = os.path.join(GRAIN_DATABASE, subgb_dict_path)
      with open(subgb_dict_path,'r') as f:
        subgb_dict = json.load(f)
      struct_path = os.path.join(subgb_model.path, subgb_model.gbid+'_traj.xyz')
      struct_path = os.path.join(GRAIN_DATABASE, struct_path)
      try:
        ats = Atoms(struct_path)
      except:
        print >> no_struct_file, struct_path
      else:
        print gb_num+start, struct_path
        try:
          forces = [np.sqrt(x**2+y**2+z**2) for x,y,z, in zip(ats.properties['force'][0], ats.properties['force'][1], ats.properties['force'][2])]
        except KeyError:
          print >> no_struct_file, struct_path
          print 'No Force in atoms object'
        if max(forces) <= force_tol:
          conv_check = True
        else:
          conv_check = False
      if modify_db:
        print struct_path
        print subgb_dict['converged'], conv_check
        subgb_dict['converged'] = conv_check
        with open(subgb_dict_path, 'w') as f:
          json.dump(subgb_dict, f, indent=2)
      else:
        print struct_path
        print subgb_dict['converged'], conv_check

def gbid_json_to_model(material='alphaFe', or_axis='001'):
#Now load the subgb.json file. and compare old converged energy 
#and new and old boolean:
  analyze  = GBAnalysis()
  gb_files = []
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, os.path.join(material, or_axis))), gb_files, 'gb.json')
  for gb in gb_files:
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    GB_model = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
    for subgb_model in GB_model.subgrains:
      subgb_dict_path = os.path.join(subgb_model.path,'subgb.json')
      subgb_dict_path = os.path.join(GRAIN_DATABASE, subgb_dict_path)
      with open(subgb_dict_path,'r') as f:
        subgb_dict = json.load(f)
      try:
        #print subgb_dict_path    
        assert subgb_dict['gbid'] == subgb_model.gbid
        if '_traj' in subgb_dict['gbid']:
          print subgb_dict['gbid'], subgb_model.gbid
          subgb_dict['gbid']= subgb_dict['gbid'].replace('_traj','')
          with open(subgb_dict_path,'w') as f:
            json.dump(subgb_dict, f, indent=2)
      except AssertionError:
        print subgb_dict['gbid'], subgb_model.gbid
        subgb_model.gbid = subgb_dict['gbid']
        subgb_model.save()
        print subgb_model.gbid

def populate_db(or_axis='001'):
  analyze  = GBAnalysis()
  dir_str  = os.path.join('alphaFe', or_axis)
  gb_files = []
#grab list of gb.json files.
  analyze.find_gb_json('{0}'.format(os.path.join(GRAIN_DATABASE, dir_str)), gb_files, 'gb.json')
  for gb in gb_files:
    print gb[0], gb[1]
    with open(gb[1], 'r') as f:
      gb_json = json.load(f)
    print gb_json
    gb_dict = {"gb_type"          : gb_json['type'],
               "n_at"             : gb_json['n_at'],
               "boundary_plane"   : serialize_vector(map(int, gb_json['boundary_plane'])),
               "orientation_axis" : serialize_vector(map(int, gb_json['orientation_axis'])),
               "z_planes"         : serialize_vector(gb_json['zplanes']),
               "coincident_sites" : gb_json['coincident_sites'],
               "angle"            : gb_json['angle'],
               "height"           : gb_json['H'],
               "area"             : gb_json['A'],
               "notes"            : "",
               "path"             : os.path.relpath(gb[0], "/home/lambert/pymodules/imeall/imeall/grain_boundaries/"),
               "gbid"             : gb_json['gbid']
              }
    print gb_dict
    try:
      GB_model_object = GrainBoundary.create(**gb_dict)
    except IntegrityError:
      GB_model_object = GrainBoundary.select().where(GrainBoundary.gbid==gb_json['gbid']).get()
      print 'GB already in database'
    subgb_files = []
    analyze.find_gb_json('{0}'.format(gb[0]), subgb_files, 'subgb.json')
    with database.atomic() as transaction:
      for subgb in subgb_files:
        print 'SUBGB', subgb
        with open(subgb[1],'r') as f:
          subgb_json = json.load(f)
        try: 
          converged = subgb_json['converged']
        except KeyError:
          converged = False
        try:
          E_gb = subgb_json["E_gb"]
        except KeyError:
          E_gb = 0.0
        try:
          E_gb_init=subgb_json["E_gb_init"]
        except KeyError:
          E_gb_init = 0.0
        try:
          gbid = subgb_json["gbid"]
        except KeyError:
          gbid = subgb_json["name"]
        try:
          area = subgb_json['A']
        except KeyError:
          structs = glob.glob(os.path.join(subgb[0], '*.xyz'))
          struct  = Atoms(structs[-1])
          cell    = struct.get_cell()
          area    = cell[0][0]*cell[1][1]
          subgb_json['n_at'] = len(struct)
          
        subgb_dict = {"canonical_grain"  : GB_model_object,
                      "converged"        : converged,
                      "E_gb_init"        : E_gb_init, 
                      "potential"        : subgb_json["param_file"],
                      "rbt"              : serialize_vector(subgb_json['rbt']),
                      "path"             : os.path.relpath(subgb[0], "/home/lambert/pymodules/imeall/imeall/grain_boundaries/"),
                      "area"             : area,
                      "rcut"             : subgb_json["rcut"],
                      "n_at"             : subgb_json['n_at'],
                      "E_gb"             : E_gb,
                      "notes"            : "",
                      "gbid"             : gbid
                    }
        try:
          SubGrainBoundary.create(**subgb_dict)        
        except IntegrityError:
          print 'GB already in DB'
          pass

if __name__=="__main__":
  #create_tables(database)
  #populate_db(or_axis="111")
  parser = argparse.ArgumentParser()
  parser.add_argument("-l", "--list",        help="List converged structures in database and their energies.", action="store_true")
  parser.add_argument("-p", "--prune",       help="Remove structures from SQL database that are no longer in directory tree.", action="store_true")
  parser.add_argument("-c", "--check_conv",  help="Check that convergence status of database json files corresponds to SQL database.", action="store_true")
  parser.add_argument("-m", "--modify",      help="Generic flag. If included database will be update, otherwise program just reports actions \
                                                   without  modifying database", action="store_true")
  parser.add_argument("-f", "--check_force", help="Inspect xyz structure files to determine if force convergence has been reached.",   action="store_true")
  args   = parser.parse_args()

  if args.list:
    oraxis = '0,0,1'
    pot_param     = PotentialParameters()
    ener_per_atom = pot_param.gs_ener_per_atom()
  
    for gb in GrainBoundary.select().where(GrainBoundary.orientation_axis==oraxis).order_by(GrainBoundary.angle):
      subgbs = (gb.subgrains.select(GrainBoundary, SubGrainBoundary)
                  .where(SubGrainBoundary.potential=='PotBH.xml')
                  .join(GrainBoundary).dicts())
  
      if len(subgbs) > 0:
        subgbs = [(16.02*(subgb['E_gb']-float(subgb['n_at']*ener_per_atom['PotBH.xml']))/(2.0*subgb['area']), subgb) for subgb in subgbs]
        subgbs.sort(key = lambda x: x[0])
        print subgbs[0][1]['potential'], gb.orientation_axis, round(gb.angle*(180.0/3.14159),2), subgbs[0][0]

  if args.prune:
    gb_conv_json_model()

  if args.check_conv:
    gb_check_conv(modify_db=args.modify)

  if args.check_force:
    gb_check_force()

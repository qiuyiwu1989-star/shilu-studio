import json,tempfile,unittest
from pathlib import Path
from shilu.core import Store
from shilu.mcp import call
class ProjectDiscovery(unittest.TestCase):
 def test_paginated_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   store=Store(Path(d)/'db.sqlite');ids=set()
   for i in range(3):
    p=call(store,'create_recap',{'config':{'title':'Test '+str(i),'author':'Speaker'},'transcript':'PRIVATE_TRANSCRIPT unique full source text'});ids.add(p['id'])
   first=call(store,'list_projects',{'limit':2});self.assertEqual(first['total'],3);self.assertTrue(first['has_more']);self.assertEqual(first['next_offset'],2)
   second=call(store,'list_projects',{'offset':first['next_offset'],'limit':2});self.assertFalse(second['has_more']);self.assertIsNone(second['next_offset'])
   self.assertEqual({p['id'] for p in first['items']+second['items']},ids)
   self.assertNotIn('PRIVATE_TRANSCRIPT',json.dumps(first));self.assertNotIn('transcript',first['items'][0]);self.assertNotIn('skill_context',first['items'][0])
   self.assertEqual(call(store,'get_project',{'project_id':first['items'][0]['id']})['id'],first['items'][0]['id'])
   for args in [{'offset':-1},{'limit':101},{'limit':0},{'offset':True}]:
    with self.assertRaises(ValueError):call(store,'list_projects',args)
   self.assertEqual(call(store,'list_projects',{'offset':100})['items'],[])

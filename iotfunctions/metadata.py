# *****************************************************************************
# Â© Copyright IBM Corp. 2018.  All Rights Reserved.
#
# This program and the accompanying materials
# are made available under the terms of the Apache V2.0
# which accompanies this distribution, and is available at
# http://www.apache.org/licenses/LICENSE-2.0
#
# *****************************************************************************

import logging
import datetime as dt
import json
import urllib3
import pandas as pd
from sqlalchemy import Table, Column, Integer, SmallInteger, String, DateTime, Float
from .db import Database, TimeSeriesTable, ActivityTable, SlowlyChangingDimension
from .automation import TimeSeriesGenerator
from .pipeline import CalcPipeline
from sqlalchemy.sql.sqltypes import TIMESTAMP,VARCHAR
from ibm_db_sa.base import DOUBLE

logger = logging.getLogger(__name__)
    
class EntityType(object):
    '''
    Data is organised around Entity Types. Entity Types have one or more 
    physical database object for their data. When creating a new Entity Type,
    it will attempt to connect itself to a table of the same name in the
    database. If no table exists the Entity Type will create one.
    
    Parameters
    ----------
    name: str
        Name of the entity type. Use lower case. Will be used as the physical
        database table name so don't use database reserved works of special
        characters. 
    db: Database object
        Contains the connection info for the database
    *args:
        Additional positional arguments are used to add the list of SQL Alchemy Column
        objects contained within this table. Similar to the style of a CREATE TABLE sql statement.
        There is no need to specify column names if you are using an existing database table as
        an entity type.
    **kwargs
        Additional keywork args. 
        _timestamp: str
            Overide the timestamp column name from the default of 'evt_timestamp'
    '''    
            
    log_table = 'KPI_LOGGING'
    checkpoint_table = 'KPI_CHECKPOINT'
    _start_entity_id = 73000 #used to build entity ids
    _auto_entity_count = 5 #default number of entities to generate data for
    
    def __init__ (self,name,db, *args, **kwargs):
        self.name = name
        self.activity_tables = {}
        self.scd = {}
        if db is None:
            db = Database()
        self.db = db        
        self._timestamp = 'evt_timestamp'
        self.set_params(**kwargs)
        try:
            self.table = self.db.get_table(self.name)
        except KeyError:
            ts = TimeSeriesTable(self.name ,self.db, *args, **kwargs)
            self.table = ts.table
            self.table.create(self.db.connection)
            
    def add_activity_table(self, name, activities, *args, **kwargs):
        '''
        add an activity table for this entity type. 
        
        parameters
        ----------
        name: str
            table name
        activities: list of strs
            activity type codes: these identify the nature of the activity, e.g. PM is Preventative Maintenance
        *args: Column objects
            other columns describing the activity, e.g. materials_cost
        '''
        kwargs['_activities'] = activities
        
        table = ActivityTable(name, self.db,*args, **kwargs)
        try:
            sqltable = self.db.get_table(name)
        except KeyError:
            table.create(self.db.connection)
        self.activity_tables[name] = table
        
        
        
    def add_slowly_changing_dimension(self,property_name,datatype):
        '''
        add a slowly changing dimension table containing a single property for this entity type
        
        parameters
        ----------
        property_name : str
            name of property, e.g. firmware_version (lower case, no database reserved words)
        datatype: sqlalchemy datatype
        '''
        
        name= '%s_scd_%s' %(self.name,property_name)

        table = SlowlyChangingDimension(name = name,
                                   database=self.db,
                                   property_name = property_name,
                                   datatype = datatype)        
        try:
            sqltable = self.db.get_table(name)
        except KeyError:
            table.create(self.db.connection)
        self.scd[property_name] = table
        
    def drop_child_tables(self):
        '''
        Drop all child tables
        '''
        tables = []
        tables.extend(self.activity_tables.values())
        tables.extend(self.scd.values())
        [self.db.drop_table(x) for x in tables]
        msg = 'dropped tables %s' %tables
        logger.info(msg)
        
    def get_params(self):
        '''
        Get entity type parameters to pass into a child object like a pipeline.
        '''
        params = {
                'entity_type_name' : self.name,
                '_timestamp' : self._timestamp,
                'db' : self.db,
                'source_table' : self.table,
                'tenant_id' : self.db.tenant_id
                }
        return params
    
    def get_calc_pipeline(self,stages=None):
        '''
        Get a CalcPipeline object
        '''
        return CalcPipeline(source=self,stages=stages)
        
        
    def get_data(self,start_ts =None,end_ts=None,entities=None):
        '''
        Retrieve entity data
        '''
        (query,table) = self.db.query(self.name)
        if not start_ts is None:
            query = query.filter(table.c[self._timestamp] >= start_ts)
        if not end_ts is None:
            query = query.filter(table.c[self._timestamp] <= end_ts)  
        if not entities is None:
            query = query.filter(table.c.deviceid.in_(entities))
        df = pd.read_sql(query.statement, con = self.db.connection)
        
        return df       
        
        
    def get_log(self,rows = 100):
        '''
        Get KPI execution log info. Returns a dataframe.
        '''
        query, log = self.db.query(self.log_table)
        query = query.filter(log.c.entity_type==self.name).\
                      order_by(log.c.timestamp_utc.desc()).\
                      limit(rows)
        df = self.db.get_query_data(query)
        return df
    
    def generate_data(self, entities = None, days=0, seconds = 300, freq = '1min', write=True):
        '''
        Generate random time series data for entities
        
        Parameters
        ----------
        entities: list
            List of entity ids to genenerate data for
        days: number
            Number of days worth of data to generate (back from system date)
        seconds: number
            Number of seconds of worth of data to generate (back from system date)
        freq: str
            Pandas frequency string - interval of time between subsequent rows of data
        write: bool
            write generated data back to table with same name as entity
        
        '''
        if entities is None:
            entities = [str(self._start_entity_id + x) for x in list(range(self._auto_entity_count))]
        metrics = []
        categoricals = []
        dates = []
        others = []
        for c in self.db.get_column_names(self.table):
            if not c in ['deviceid','devicetype','format','updated_utc','logicalinterface_id',self._timestamp]:
                data_type = self.table.c[c].type
                if isinstance(data_type,DOUBLE) or isinstance(data_type,Float):
                    metrics.append(c)
                elif isinstance(data_type,VARCHAR) or isinstance(data_type,String):
                    categoricals.append(c)
                elif isinstance(data_type,TIMESTAMP) or isinstance(data_type,DateTime):
                    dates.append(c)
                else:
                    others.append(c)
                    msg = 'Encountered column %s of unknown data type %s' %(c,data_type.__class__.__name__)
                    raise TypeError(msg)
        msg = 'Generating data for %s with metrics %s and dimensions %s and dates %s' %(self.name,metrics,categoricals,dates)
        logger.debug(msg)
        ts = TimeSeriesGenerator(metrics=metrics,ids=entities,days=days,seconds=seconds,freq=freq, categoricals = categoricals, dates = dates)
        df = ts.execute()
        if write:
            for o in others:
                if o not in df.columns:
                    df[o] = None
            df['logicalinterface_id'] = ''
            df['devicetype'] = self.name
            df['format'] = ''
            df['updated_utc'] = None
            self.db.write_frame(table_name = self.name, df = df)
            
        for at in list(self.activity_tables.values()):
            adf = at.generate_data(entities = entities, days = days, seconds = seconds, write = write)
            msg = 'generated data for activity table %s' %at.name
            logger.debug(msg)
            
        for scd in list(self.scd.values()):
            sdf = scd.generate_data(entities = entities, days = days, seconds = seconds, write = write)
            msg = 'generated data for scd table %s' %scd.name
            logger.debug(msg)
        
        return df
    
    def register(self):
        '''
        Register entity type so that it appears in the UI. Create a table for input data.
        
        Parameters
        ----------
        credentials: dict
            credentials for the ICS metadata service

        '''
        columns = []
        dates = []
        for c in self.db.get_column_names(self.table):
            if c not in ['logicalinterface_id','format','updated_utc']:
                data_type = self.table.c[c].type
                if isinstance(data_type,DOUBLE):
                    data_type = 'NUMBER'
                elif isinstance(data_type,TIMESTAMP):
                    data_type = 'TIMESTAMP'
                    dates.append(c)
                elif isinstance(data_type,VARCHAR):
                    data_type = 'LITERAL'
                else:
                    data_type = str(data_type)
                columns.append({ 
                        'name' : c,
                        'type' : 'METRIC',
                        'columnName' : c,
                        'columnType'  : data_type,
                        'tags' : None,
                        'transient' : False
                        })
        table = {}
        table['name'] = self.name
        table['dataItemDto'] = columns
        table['metricTableName'] = self.name
        table['metricTimestampColumn'] = self._timestamp
        table['schemaName'] = self.db.credentials['db2']['username']
        payload = [table]
        response = self.db.http_request(request='POST',
                                     object_type = 'entityType',
                                     object_name = self.name,
                                     payload = payload)

        msg = 'Metadata registerd for table %s '%self.name
        logger.debug(msg)
        return response
    
    def set_dimension_columns(self,columns):
        '''
        TBD Add dimension table by specifying additional columns
        '''
        pass
    
    def set_params(self, **params):
        '''
        Set parameters based using supplied dictionary
        '''
        for key,value in list(params.items()):
            setattr(self, key, value)
        return self        
        
        
        
        

        
            
            
    
    
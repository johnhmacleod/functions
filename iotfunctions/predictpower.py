class PredictPower(BaseTransformer):
    '''
    Predict freezer power usage from ambient temperature, humidity & hour of day V7
    '''
    
    def __init__(self, temperature, humidity, hourofday, predictedpower = 'predictedpower'):
        self.temperature = temperature
        self.humidity = humidity
        self.hourofday = hourofday
        self.predictedpower = predictedpower
        
        super().__init__()

    def execute(self, df):
        df = df.copy()
        wml_credentials={
            "url": "https://us-south.ml.cloud.ibm.com",
            "username": "8c34c270-1e1c-4052-ae39-6327b0379281",
            "password": "f18edf22-940a-4907-be66-90446b7e42cc"
        }

        headers = urllib3.util.make_headers(basic_auth='{username}:{password}'.format(username=wml_credentials['username'], password=wml_credentials['password']))
        url = '{}/v3/identity/token'.format(wml_credentials['url'])
        response = requests.get(url, headers=headers)
        mltoken = json.loads(response.text).get('token')

        output = []
        header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + mltoken}
        
        for index, row in df.iterrows():
            payload_scoring = {"fields": ["AVGTEMP", "AVGHUMIDITY", "HOUROFDAY"], "values": [[row[self.temperature],row[self.humidity],row[self.hourofday]]]}
            response_scoring = requests.post('https://us-south.ml.cloud.ibm.com/v3/wml_instances/c406a8c1-5aae-4934-887a-29871d186f00/deployments/c69641c7-65d1-43d6-a539-0d92147f49a9/online', json=payload_scoring, headers=header)
            result = json.loads(response_scoring.text)
            output.append(result.get('values')[0][4])
            
        df[self.predictedpower] = output
        return df 
    
    @classmethod
    def build_ui(cls):
        #define arguments that behave as function inputs
        inputs = OrderedDict()
        inputs['temperature'] = UISingleItem(name = 'temperature',
                                              datatype=float,
                                              description = 'Temperature in C',
                                              required = True,
                                              )
        inputs['humidity'] = UISingle(name = 'humidity',
                                              datatype=float,
                                              description = 'Humidity in %',
                                              required = True,
                                              )
        inputs['hourofday'] = UISingle(name = 'hourofday',
                                              datatype=float,
                                              description = 'Hour of day',
                                              required = True,
                                              )  
        #define arguments that behave as function outputs
        outputs = OrderedDict()
        outputs['predictedpower'] = UIFunctionOutSingle(name = 'predictedpower',
                                                     datatype=float,
                                                     description='Predicted power consumption',
                                                     )
        return (inputs,outputs)

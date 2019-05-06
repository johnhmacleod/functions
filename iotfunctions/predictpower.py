class PredictPower(BaseTransformer):
    '''
    Predict freezer power usage from ambient temperature, humidity & hour of day
    '''
    
    def __init__(self, input_item_1, input_item_2, input_item_3, output_item = 'output_item'):
        self.input_item_1 = input_item_1
        self.input_item_2 = input_item_2
        self.input_item_3 = input_item_3
        self.output_item = output_item
        
        super().__init__()

    def execute(self, df):
        df = df.copy()
        wml_credentials={
            "url": "https://us-south.ml.cloud.ibm.com",
            "username": "07ccaa7c-a1a3-4323-90d2-d6ea672d2cab",
            "password": "3e6d9a9a-5a59-4f34-93a2-0cfc9e31eb1e"
        }

        headers = urllib3.util.make_headers(basic_auth='{username}:{password}'.format(username=wml_credentials['username'], password=wml_credentials['password']))
        url = '{}/v3/identity/token'.format(wml_credentials['url'])
        #response = requests.get(url, headers=headers)
        #mltoken = json.loads(response.text).get('token')

        #header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + mltoken}

        #payload_scoring = {"fields": ["AVGTEMP", "AVGHUMIDITY", "HOUROFDAY"], "values": [[df[self.input_item_1],df[self.input_item_2],df[self.input_item_3]]]}

        #response_scoring = requests.post('https://us-south.ml.cloud.ibm.com/v3/wml_instances/c406a8c1-5aae-4934-887a-29871d186f00/deployments/c69641c7-65d1-43d6-a539-0d92147f49a9/online', json=payload_scoring, headers=header)
        #print("Scoring response")
        #print(json.loads(response_scoring.text))    
        
        #df[self.output_item] = response_scoring.values[0][4];
        #df[self.output_item] = 70;
return df 

import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium
import math
import io

addressColumnName = "Billing Address"
detailColumnName = "Customer full name"
phoneColumnName = "Phone Numbers"

@st.cache_data
def geocode_address(address):
    print("Pinging census")
    print(address)
    
    # Base URL for the Census Geocoding API
    base_url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress&key=48b0180a950a3b41c8c4891b04dad226979c18c6"
    
    # Parameters for the API request
    params = {
        'address': address,
        'benchmark': 'Public_AR_Current',
        'format': 'json'
    }
    
    # Make a GET request to the API
    response = requests.get(base_url, params=params)
    
    # st.write(f"Response content: {response.content}")

    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()
        
        # Extract latitude and longitude from the response
        if 'result' in data and 'addressMatches' in data['result']:
            matches = data['result']['addressMatches']
            if matches:
                first_match = matches[0]
                coordinates = first_match['coordinates']
                return coordinates['y'], coordinates['x']  # Return latitude, longitude
    
    # Handle errors or no matches found
    #print(response.json())
    return None, None

# Function to add latitude and longitude columns to DataFrame
@st.cache_data
def add_geocoding(df, saveToFile=True):
    #st.write("rerunning add_geocoding")
    latitudes = []
    longitudes = []
    
    for index, row in df.iterrows():
        address = row[addressColumnName]
        
        # Only geocode if latitude and longitude are not already present for this row
        if 'latitude' not in row or 'longitude' not in row or pd.isna(row['latitude']) or pd.isna(row['longitude']):
            lat, lng = geocode_address(address)
            latitudes.append(lat)
            longitudes.append(lng)
        else:
            latitudes.append(row['latitude'])
            longitudes.append(row['longitude'])
    
    df['latitude'] = latitudes
    df['longitude'] = longitudes
    
    if (saveToFile):
        output_file = uploaded_file
        if (saveType == "csv"):
            df.to_csv(output_file, index=False)
        else:
            df.to_excel(uploaded_file, index=False)

    return df

@st.cache_data
def haversine_distance(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    distance = 3956 * c  # radius of earth in miles

    return distance

def create_map():
    # mequonCoords = [43.235641680318786, -87.97286701369205]
    # Create the map with Google Maps
    map_obj = folium.Map(st.session_state.clicked_coords, zoom_start=5)
    # map_obj = folium.Map(location=mequonCoords, tiles=None, zoom_start=13)
    # folium.TileLayer("https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", 
    #                  attr="google", 
    #                  name="Google Maps", 
    #                  overlay=True, 
    #                  control=True, 
    #                  subdomains=["mt0", "mt1", "mt2", "mt3"]).add_to(map_obj)
    return map_obj

def add_markers(map_obj, df_filtered, centerCoords):
    for index, row in df_filtered.iterrows():
        lat, lon = row['latitude'], row['longitude']
        popup = f"{row[detailColumnName]}<br>{row[addressColumnName]}<br>{row[phoneColumnName]}"
        folium.Marker([lat, lon], popup=popup).add_to(map_obj)

    # Fit the map bounds to include all markers
    #df_filtered.loc[len(df_filtered)] = ['Placeholder center address', 'Placeholder center name', centerCoords[0], centerCoords[1], 0]

    if not df_filtered.empty:
        south_west = [df_filtered['latitude'].min() - 0.02, df_filtered['longitude'].min() - 0.02]
        north_east = [df_filtered['latitude'].max() + 0.02, df_filtered['longitude'].max() + 0.02]
        map_bounds = [south_west, north_east]
        map_obj.fit_bounds(map_bounds)

    return map_obj

def add_center_marker(map_obj, lat, lon, color='red', icon='star', popup=None):
    new_marker = folium.Marker([lat, lon], draggable=True, icon=folium.Icon(color=color, icon=icon), popup=popup)
    map_obj.add_child(new_marker)

    return map_obj

def miles_to_meters(miles):
    return miles * 1609.34

# START HERE

# Latitudes and longitudes get saved if they are changed/added to the spreadsheet
whetherToSave = True
# When latitudes and longitudes are added, the dataframe is saved to the same file that was read from
saveType = "excel"

st.sidebar.title("Rain Dance Mapping Tool")
st.sidebar.write("Upload an excel or csv file to see client locations!")            
    
# Create a file uploader in the sidebar
uploaded_file = st.sidebar.file_uploader("Choose a file", type=["csv", "xlsx", "xls"])

skipRowCount = 3

if uploaded_file is not None:
    # Determine the file type and read accordingly
    if uploaded_file.name.endswith('.csv'):
        df_sample = pd.read_csv(uploaded_file)
        saveType = "csv"
    elif uploaded_file.name.endswith(('.xlsx', '.xls')):
        df_sample = pd.read_excel(uploaded_file, skiprows=skipRowCount)
        saveType = "excel"

    df_copy = df_sample.copy()
    df_sample = add_geocoding(df_sample)
    whetherToSave = (not df_sample.equals(df_copy))

    # If the dataframes have been modified, then a download button is created for the modified version
    if(whetherToSave):
        st.sidebar.write("Data has been modified! Redownload a new spreadsheet below to make this site faster next time (so we don't have to re-look up the latitudes and longitudes every time).")
        
        if (saveType == "csv"):
            # csvs are relatively simple to save
            st.sidebar.download_button(
                label="Download data",
                data=df_sample.to_csv().encode('utf-8'),
                file_name=uploaded_file.name,
                mime='text/csv',
            )
        else:
            # excel files are a bit trickier. This saves to a stream which is then pumped into the streamlit button
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_sample.to_excel(writer, index=False, sheet_name='Sheet1')
                writer.close()

            # Set the file position to the beginning
            output.seek(0)
            st.sidebar.download_button(
                label="Download data",
                data=output,
                file_name=uploaded_file.name,
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )

    if "clicked_coords" not in st.session_state:
        st.session_state.clicked_coords = [43.235641680318786, -87.97286701369205]

    m = create_map()

    # Define the default value for the slider
    default_value = 4

    num_miles_away = st.sidebar.slider('Work range from point of interest (miles):', min_value=1, max_value=50, 
                                    value=default_value)

    st.session_state.num_miles_away = num_miles_away

    # Calculate the distances from point of interest
    df_sample['distance_from_poi_miles'] = df_sample.apply(lambda x: haversine_distance(x['latitude'], 
                                                                    x['longitude'], 
                                                                    st.session_state.clicked_coords[0], 
                                                                    st.session_state.clicked_coords[1]), axis=1)

    df_filtered = df_sample[df_sample['distance_from_poi_miles'] < num_miles_away]

    m = add_markers(m, df_filtered, st.session_state.clicked_coords)

    add_center_marker(m, st.session_state.clicked_coords[0], st.session_state.clicked_coords[1], popup='Point of Interest')

    map_data = st_folium(m, width=700, height=500, returned_objects = ["last_clicked"])

    if map_data and map_data["last_clicked"]:
        clicked_coords = map_data["last_clicked"]
        st.session_state.clicked_coords = [clicked_coords['lat'], clicked_coords['lng']]
        st.experimental_rerun()
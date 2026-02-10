import osmnx as ox

# Указываем город
city = "Москва, Россия"
# Запрашиваем объекты с тегом 'station' и 'subway'
metro_stations = ox.features_from_place(city, tags={'railway': 'station', 'station': 'subway'})

# На выходе получаем таблицу (GeoDataFrame) с координатами
print(metro_stations[['name', 'geometry']].head())
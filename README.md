#mp3 movie api

This project is a fastAPi application that stores a single movie collection in SQLite and then serves it through a REST API. 'main.api' defines the endpoints 'src/database.py' creates connections and the 'movies' table, and 'src/storage.py' contains'MovieStorage', which saves, retireves, filters,a nd counts movies using SQL. uploading a CSV through POSt/upload checks that it has exactly the columns title, release_year, rating, and genre, then replaces the stored collections in one transaction! GEt movies/search filters by min rating and returns requested columns through a parameterized sql query and post/movies/process reuses the mp1 data_pipeline functions to validate and clean the stored moveis, and then saves the result back to sqlite . src/cache.py caches GET/movies responses into fake redis for 90 seconds and is keyed by the limit. successful oploads or processings run clears the cache, so api never srves outdated  data


to start:

python -m uvicorn main:app --reload

for tests:

python -m pytest tests -v
import base64
import datetime
import decimal
import json
import os
import pyodbc
import quart
import quart_cors
from quart import request
from http.client import HTTPException
import logging

cnxn = None
app = quart_cors.cors(quart.Quart(__name__), allow_origin="https://chat.openai.com")

@app.get("/logo.png")
async def plugin_logo():
    filename = 'logo.png'
    return await quart.send_file(filename, mimetype='image/png')

@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    host = request.headers['Host']
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")

@app.get("/openapi.yaml")
async def openapi_spec():
    host = request.headers['Host']
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")


@app.post("/connect-to-database")
async def connect_to_database():
    global cnxn
    host = os.environ.get("DB_HOST", "gnvadev.database.windows.net")
    user = os.environ.get("DB_USER", "KonTesting")
    password = os.environ.get("DB_PASSWORD", "f6J@yMzsyKhAb_Gy")
    database = os.environ.get("DB_DATABASE", "KonTesting")
    port = os.environ.get("DB_PORT", "1433")
    driver= '{ODBC Driver 17 for SQL Server}'
    cnxn = pyodbc.connect('DRIVER='+driver+';SERVER='+host+';PORT=1433;DATABASE='+database+';UID='+user+';PWD='+ password)

    result = "Established connection to Shell's Oil & Gas database."
    return quart.Response(response=result, status=200)


@app.get("/get-table-schemas")
async def get_table_schemas():
    if cnxn is None:
        await connect_to_database()

    cursor = cnxn.cursor()
    cursor.execute("SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS")
    rows = cursor.fetchall()
    if rows:
        table_schemas = {}
        for row in rows:
            table_name = row[0]
            column_name = row[1]
            data_type = row[2]
            if table_name not in table_schemas:
                table_schemas[table_name] = {}
            table_schemas[table_name][column_name] = data_type
        return json.dumps(table_schemas)
    return "No table schemas found."


@app.get("/get-schema-name/<table_name>")
async def get_schema_name(table_name: str):
    if cnxn is None:
        await connect_to_database()

    try:
        cursor = cnxn.cursor()
        logging.info("The user provided table name is: %s")
        query = f"SELECT TABLE_SCHEMA FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table_name}'"
        cursor.execute(query)
        row = cursor.fetchone()

        if row:
            return {"table_name": table_name, "schema_name": row[0]}
        else:
            raise HTTPException(status_code=404, detail=f"No schema found for table {table_name}.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-tables")
async def get_tables():
    if cnxn is None:
        await connect_to_database()

    cursor = cnxn.cursor()
    logging.info(cursor)
    cursor.execute("SELECT name FROM sys.tables")
    rows = cursor.fetchall()
    if rows:
        return [row[0] for row in rows]
    return "No tables have been found."


@app.get("/get-columns/<table_name>")
async def get_columns(table_name):
    if cnxn is None:
        await connect_to_database()

    cursor = cnxn.cursor()
    logging.info(cursor)
    cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'")
    rows = cursor.fetchall()
    if rows:
        return [row[0] for row in rows]
    return f"No columns found for table {table_name}."


@app.post("/execute-sql-query")
async def execute_sql_query():
    if not cnxn or cnxn.closed:
        await connect_to_database()

    request = await quart.request.get_json(force=True)
    query = request["query"]
    logging.info(f"Executing SQL query: {query}")
    cursor = cnxn.cursor()

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        if rows:
            # Convert rows to list of dictionaries
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]

            # Handle non-serializable data types
            for result in results:
                for key, value in result.items():
                    if isinstance(value, decimal.Decimal):
                        result[key] = float(value)
                    elif isinstance(value, datetime.datetime):
                        result[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(value, bytes):
                        result[key] = base64.b64encode(value).decode('utf-8')

            return results
        return "No results found for the query."
    except pyodbc.ProgrammingError as e:
        logging.error(f"Error executing SQL query: {e}")
        return f"Error executing SQL query: {str(e)}", 500



def main():
    app.run(debug=True, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()

import uvicorn

if __name__ == "__main__":
    uvicorn.run("Bot_mini_map_ai.api.main:app", host="0.0.0.0", port=8001, reload=True)

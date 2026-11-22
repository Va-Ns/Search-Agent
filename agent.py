import ollama
from ddgs import DDGS


# ---------- 1. The tool ----------
# The model never sees this code. It sees only the name, the type hint and the docstring
def web_search(query:str) -> str:
    """
        Search the web and return the top 5 results (title, link, snippet).

        Args:
            query: what to search for, phrased like a search-engine query
    """

    try:


        results = DDGS().text(query, max_results=5)

    except Exception as e:

        return f"Search failed: {e}" # Tell the model what went wrong instead of just crashing

    return "\n\n".join(
        
            f"[{i}] {r['title']}\nURL: {r['href']}\nSnippet: {r['body']}"
            
            for i, r in enumerate(results, 1)
                      )


# ---------- 2. Settings ----------
MODEL = "qwen3:8b"
MAX_STEPS = 5 # We put a safety cap of 5 model calls per question

messages = [
                {"role": "system",
                 "content": "You are a helpful assistant running in a loop with access to a web_search tool. "
                                  "Use it for anything recent or factual you are unsure about. You may call it several times. "
                                  "Search results often contain some irrelevant entries: ignore those and use the relevant ones. "
                                  "If the results are poor, search again with a different, more specific query; "
                                  "never repeat the same query. "
                                  "Base your answer on the search results and end it with a 'Sources:' list of the URLs you used."
                }
            ]


# ---------- 3. The agent loop ----------
while True:

    question = input("\nYou: ")

    if question.lower() in ("quit", "exit"):

        break

    messages.append(
                    {"role": "user",
                     "content": question}
                    )

    for step in range(MAX_STEPS):

        response = ollama.chat(model = MODEL, messages = messages, tools = [web_search])

        messages.append(response.message) # Remember what the model said

        if not response.message.tool_calls: # If the tool was not requested, then we have our final answer

            break

        for call in response.message.tool_calls: # In the case where the model does call the tool

            print(f"  [step  {step+1}] {call.function.name}({call.function.arguments})")

            result = web_search(**call.function.arguments)

            for line in result.splitlines():
                
                if line.startswith("["):        # only the numbered title lines
                    
                    print("      " + line)

            messages.append(
                            {"role": "tool",
                             "content": result,
                             "tool_name": call.function.name}
                           )
    else:

        print("  [stopped: reached MAX_STEPS]")

    print("\nAgent: ", response.message.content)

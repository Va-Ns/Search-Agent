import ollama
import trafilatura
from ddgs import DDGS


# ---------- 1. Tools ----------
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

MAX_PAGE_CHARS = 12000 # about 3k tokens, so two pages fit in the context

def read_page(url: str) -> str: 

    """

        Open a web page and return its main text (no menus or ads).
        Use it on the most relevant search results when the snippets are not enough.

        Args: 

            url: the full address of the page, copied from a search result.

    """

    html = trafilatura.fetch_url(url)

    if html is None: 

        return f"Couldn't fetch {url}. Try another result."

    text = trafilatura.extract(html)

    if not text: 

        return f"No readable text found at {url} (the page may need JavaScript). Try another result."

    if len(text) > MAX_PAGE_CHARS:

        text = text[:MAX_PAGE_CHARS] + "\n\n[page truncated]"

    return text

TOOLS = {"web_search": web_search, "read_page": read_page} # Every entry of dictionary points to the corresponding function.


# ---------- 2. Settings ----------
MODEL = "qwen3:8b"
MAX_STEPS = 8 # With the search + reading of pages, we need more rounds
CONTEXT_TOKENS = 16384 

messages = [
                {"role": "system",
                 "content": "You are a helpful assistant running in a loop with two tools: "
                            "web_search to find pages and read_page to read a page in full. "
                            "For anything recent or factual you are unsure about, search first. "
                            "Search results often contain some irrelevant entries: ignore those. "
                            "If the snippets do not fully answer the question, use read_page on the "
                            "one or two most relevant results. "
                            "If results are poor, search again with a different, more specific query; "
                            "never repeat the same query. "
                            "Base your answer on what you found and end it with a 'Sources:' list of the URLs you used."
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

        response = ollama.chat(model = MODEL, 
                               messages = messages, 
                               tools = list(TOOLS.values()),
                               options = {"num_ctx": CONTEXT_TOKENS}

        )

        messages.append(response.message) # Remember what the model said

        if not response.message.tool_calls: # If the tool was not requested, then we have our final answer

            break

        for call in response.message.tool_calls: # In the case where the model does call the tool

            name, args = call.function.name, call.function.arguments

            print(f"  [step  {step+1}] {name}({args})")

            function = TOOLS.get(name)

            if function is None: 

                result = f"Unknown tool: {name}. Available tools: {', '.join(TOOLS)}."

            else: 

                result = function(**args)
                
            # Trace: show what came back 

            if name == "web_search": 

                for line in result.splitlines(): 

                    if line.startswith("["):

                        print("     " + line)

            else: 

                print(f"     returned {len(result)} characters: {result[:80]!r}...")

            messages.append(
                            {"role": "tool",
                             "content": result,
                             "tool_name": name}
                           )
        else: 

            print("  [stopped: reached MAX_STEPS]")

        print("\nAgent:", response.message.content)
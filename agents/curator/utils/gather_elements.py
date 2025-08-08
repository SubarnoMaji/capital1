import json
import time
import re
import asyncio
import random
import string
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import aiohttp
from functools import partial

import os
import sys

# Add the parent directory (project root) to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nest_asyncio

nest_asyncio.apply()

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from utils.tools.search_tool import GoogleSearchTool
from utils.tools.image_search_tool import GoogleImageSearchTool
from utils.tools.suggestions_logger import SuggestionDataLoggerTool


class ElementDetailGatherer:
    """
    A class responsible for gathering comprehensive details for highlighted elements
    in curated suggestions, including images, summaries, reviews, timings, and contact information.
    """

    def __init__(self, model):
        """
        Initialize the ElementDetailGatherer with a language model.

        Args:
            model: Language model for processing and structuring information
        """
        self.model = model
        self.google_search_tool = GoogleSearchTool()
        self.image_search_tool = GoogleImageSearchTool()
        self.thread_pool = ThreadPoolExecutor(
            max_workers=10
        )  # Adjust based on your CPU cores
        self.session = None  # Will be initialized in gather_element_details

    async def _init_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def _close_session(self):
        if self.session:
            await self.session.close()
            self.session = None

    def generate_random_id(self, length=10):
        characters = string.ascii_letters + string.digits
        return "".join(random.choice(characters) for _ in range(length))

    async def fetch_images(self, item_name: str) -> List[str]:
        try:
            image_results = await self.image_search_tool._arun(
                query=f"{item_name}", k=3
            )
            return [img["Image Link"] for img in image_results] if image_results else []
        except Exception as e:
            print(f"Error fetching images for {item_name}: {e}")
            return []

    async def fetch_search_results(self, item_name: str, query_type: str) -> List[Dict]:
        try:
            query = f"{item_name} {query_type}"
            return await self.google_search_tool._arun(query=query, k=3)
        except Exception as e:
            print(f"Error fetching {query_type} for {item_name}: {e}")
            return []

    async def process_llm_response(
        self, item_name: str, search_results: List[Dict]
    ) -> Dict:
        try:
            detailed_info = "\n\n".join(
                [
                    f"Title: {result.get('Title', '')}\nContent: {result.get('Content', '')}"
                    for result in search_results
                ]
            )

            curator_message = HumanMessage(
                content=f"""
                Please extract the following information about "{item_name}" from these search results:

                {detailed_info}

                Format the response as a JSON object with these fields, with both keys and values within double quotes:
                1. summary: A 2-3 sentence summary about this place/activity and a little bit about nearby places to visit
                2. reviews: Quantified ratings (eg: 4/5)
                3. timings: Opening hours or availability (if it is a landmark or activity. For hotels, find check-in/check-out timings. Else '')
                4. contact_info: Any available contact information (phone, email, website) using markdown formatting (again for specific places only, not for general locations)
                5. nearby_attractions: Nearby attractions or activities (like restaurants, parks, etc.) as a string
                6. cost: Information about cost is given here: {detailed_info}. From this, please extract the cost information and return it in the following format:
                    -- Return either a specific value or a narrow, realistic range in the local currency of the place or activity.
                    -- If the place or activity is free, return "Free".
                    -- Avoid listing multiple itemized prices (e.g., parking, child vs adult rates, extras). Instead, consolidate similar prices into a single summarized value or range. But if the itemized prices are too different, then you can return them as it is but try to group them into 1-3 compact categories only if needed (e.g., "Entry: 0-20", "Day Pass: 200-450").
                    -- Round values for readability: Make sure you always round up only. Never do it down.
                        --- Round up to the nearest 50 for amounts between 10-100, Round up to the nearest 100 for 100-1000, Round up to the nearest 1000 for anything above 1000.
                        --- If the result is approximate, prefix with "Around" (e.g., "Around AED 300" or "Around USD 500-1500"). But use "Around" only if the estimate feels imprecise or loosely inferred; otherwise, return just the rounded number or range without it.
                    -- If you encounter a wide spread of values, return the most common or general range a visitor might expect, not outlier prices.
                    -- The output must be a single, concise line—no explanations or extra text.
                    -- If no meaningful cost information is present, return an empty string: "".

                Return only the JSON object without any explanation or additional text.
                """
            )

            info_response = await self.model.ainvoke([curator_message])
            response_text = info_response.content

            # Extract JSON if wrapped in code blocks
            if "```json" in response_text:
                response_text = (
                    response_text.split("```json")[1].split("```")[0].strip()
                )
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            return json.loads(response_text)
        except Exception as e:
            print(f"Error processing LLM response for {item_name}: {e}")
            return {
                "summary": f"Information about {item_name}",
                "reviews": [],
                "timings": "Information not available",
                "contact_info": "Information not available",
            }

    async def fetch_info(self, item_name: str) -> Dict:
        try:
            # Fetch all search results in parallel
            search_tasks = [
                self.fetch_search_results(item_name, "detailed information"),
                self.fetch_search_results(item_name, "ratings and reviews"),
                self.fetch_search_results(item_name, "opening hours and timings"),
                self.fetch_search_results(item_name, "contact information"),
                self.fetch_search_results(item_name, "nearby attractions and places"),
                self.fetch_search_results(
                    item_name, "cost per person or entry fee or ticket price"
                ),
            ]

            all_results = await asyncio.gather(*search_tasks)
            flattened_results = [
                result for results in all_results for result in results
            ]

            return await self.process_llm_response(item_name, flattened_results)
        except Exception as e:
            print(f"Error fetching details for {item_name}: {e}")
            return {
                "summary": f"Information about {item_name}",
                "reviews": [],
                "timings": "Information not available",
                "contact_info": "Information not available",
            }

    async def process_element(self, item_name: str, element_id: str) -> Dict:
        # Create tasks for both image search and info search to run in parallel
        structured_info_task = self.fetch_info(item_name)
        image_urls_task = self.fetch_images(item_name)

        # Wait for both tasks to complete
        structured_info, image_urls = await asyncio.gather(
            structured_info_task, image_urls_task
        )

        return {
            "element_id": element_id,
            "name": item_name,
            "thumbnail": image_urls,
            "summary": structured_info.get("summary", ""),
            "reviews": structured_info.get("reviews", []),
            "timings": structured_info.get("timings", ""),
            "contact_info": structured_info.get("contact_info", ""),
            "nearby_attractions": structured_info.get("nearby_attractions", ""),
            "cost": structured_info.get("cost", ""),
        }

    def process_element_sync(self, item_name: str, element_id: str) -> Dict:
        """Synchronous version of process_element for ThreadPoolExecutor"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.process_element(item_name, element_id))
        finally:
            loop.close()

    async def gather_element_details(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gathers comprehensive details for highlighted elements including images,
        summary, reviews, timings, and contact information with fully parallel execution.

        Args:
            state: Current state of the agent

        Returns:
            Updated agent state with detailed element information
        """
        print("CuratorNode: Starting Parallelized Element Detail Gatherer")
        start_time = time.time()

        await self._init_session()

        try:
            # Check if curated_suggestions exist in state
            if "curated_suggestions" not in state:
                if (
                    "message_from_curator" in state
                    and "suggestions" in state["message_from_curator"]
                ):
                    state["curated_suggestions"] = state["message_from_curator"][
                        "suggestions"
                    ]
                else:
                    print("No curated suggestions found in state")
                    return state

            suggestion_logger_tool = SuggestionDataLoggerTool()

            # Make sure we have a conversation_id
            conversation_id = state.get("message_to_curator", {}).get(
                "conversation_id", ""
            )
            if not conversation_id and "message_from_curator" in state:
                conversation_id = self.generate_random_id(15)
                if "message_to_curator" not in state:
                    state["message_to_curator"] = {}
                state["message_to_curator"]["conversation_id"] = conversation_id

            # Get previous element details
            previous_element_details = (
                await suggestion_logger_tool._arun(
                    action="retrieve", key=conversation_id
                )
                if conversation_id
                else "[]"
            )

            try:
                previous_details = json.loads(previous_element_details)
            except json.JSONDecodeError:
                previous_details = []

            all_element_details = {}

            # Process each suggestion
            for suggestion in state["curated_suggestions"]:
                suggestion_id = suggestion["suggestion_id"]
                content = suggestion["content"]
                highlighted_item_pattern = re.compile(r"\*\*(.*?)\*\*")
                matches = highlighted_item_pattern.findall(content)

                if not matches:
                    continue

                # Get key place topic from first match
                key_place_topic = matches[0]
                # Use remaining matches for elements
                matches = matches[1:]

                # Generate IDs for each highlighted item
                element_ids = {
                    item_name: self.generate_random_id() for item_name in matches
                }

                # Collect previously fetched elements
                elements_fetched_details = {}
                for item in previous_details:
                    for value in item.get("element_details", {}).values():
                        if "name" in value:
                            elements_fetched_details[value["name"]] = value

                # Determine which elements need to be fetched
                new_matches = [
                    match for match in matches if match not in elements_fetched_details
                ]

                # Process new elements in parallel using ThreadPoolExecutor
                element_results = []
                if new_matches:
                    futures = []
                    for match in new_matches:
                        element_id = element_ids[match]
                        # Add key_place_topic to the search context
                        future = self.thread_pool.submit(
                            self.process_element_sync, f"{match} - {key_place_topic}", element_id
                        )
                        futures.append((match, element_id, future))

                    # Process completed futures as they come in
                    for match, element_id, future in futures:
                        try:
                            result = future.result()
                            # Update the name to remove the key_place_topic suffix
                            result["name"] = match
                            element_results.append(result)
                        except Exception as e:
                            print(f"Error processing element {match}: {e}")

                # Process results
                element_details = {}
                for match in matches:
                    element_id = element_ids[match]
                    if match in elements_fetched_details:
                        element_details[element_id] = elements_fetched_details[match]
                    else:
                        element_result = next(
                            (
                                result
                                for result in element_results
                                if result["element_id"] == element_id
                            ),
                            None,
                        )
                        if element_result:
                            element_details[element_id] = element_result
                        else:
                            print(f"Element result not found for {match}")

                # Update the suggestion with the elements_details
                suggestion["element_details"] = element_details

                # Aggregate for logging
                all_element_details.update(element_details)

                # Log the updated element details
                if conversation_id and all_element_details:
                    await suggestion_logger_tool._arun(
                        action="update",
                        data={"element_details": element_details},
                        key=conversation_id,
                        suggestion_id=suggestion_id,
                    )

            total_time = time.time() - start_time
            num_elements = sum(
                len(suggestion.get("element_details", {}))
                for suggestion in state["curated_suggestions"]
            )

            if num_elements > 0:
                print(
                    f"CuratorNode: Parallelized Element Detail Gatherer Completed in {total_time:.2f} seconds"
                )
                print(f"Elements processed: {num_elements}")

            return state

        finally:
            await self._close_session()


async def main():
    model = ChatOpenAI(model="gpt-4o")
    gatherer = ElementDetailGatherer(model)

    # Example state
    state = {
        "message_to_curator": {
            "query": "can you tell me about Baga beach?",
            "conversation_id": "xyz12",
        },
        "curated_suggestions": [
            {
                "suggestion_id": "BagaBeach1",
                "content": "## **Arsalan, Jadavpur**, **Aminia, Tollygunge**, **Victoria Memorial**, **Birla Planetarium**, **Science City, Kolkata**",
                "status": "to_be_approved",
                "reference_urls": [
                    "https://en.tripadvisor.com.hk/ShowTopic-g297604-i6045-k14743665-Goa_in_june-Goa.html",
                    "https://www.tripadvisor.com/ShowTopic-g297604-i6045-k14743665-Goa_in_june-Goa.html",
                    "https://ricardoandlorena.com/gap-year-adventures/things-to-do-in-goa",
                    "https://www.goa.app/blog/baga-beach",
                    "https://goantales.com/travel-guides/baga-beach-goa/",
                ],
                "timestamp": "2025-04-17T04:41:19.745458",
            }
        ],
    }

    # Gather element details if needed
    updated_state = await gatherer.gather_element_details(state)
    print("Elements details gathered successfully")
    print(updated_state)


if __name__ == "__main__":
    asyncio.run(main())

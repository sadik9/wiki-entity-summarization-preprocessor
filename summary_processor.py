import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from commons.storage import fetch_unprocessed_wikipedia_pages, mark_wikipedia_page_process_failed
from commons.wiki_entity import WikiEntity
from commons.wiki_mapping import WikiMapping


def process_row(wikipedia_id):
    try:
        wiki_mapping = WikiMapping(wikipedia_id)
        if not wiki_mapping.wikidata_id or not wiki_mapping.wikipedia_page_title:
            # Pages without a Wikidata mapping used to stay `processed = FALSE` forever (the failure was marked on a
            # None id), so the main loop kept fetching them again and never terminated.
            mark_wikipedia_page_process_failed(wikipedia_id)
            return
        WikiEntity(wiki_mapping).get_summaries(False)
    except Exception as e:
        print(f"Error processing {wikipedia_id}: {e}")
        try:
            mark_wikipedia_page_process_failed(wikipedia_id)
        except Exception as mark_error:
            print(f"Error marking {wikipedia_id} as failed: {mark_error}")


if __name__ == '__main__':
    counter = 0
    with ThreadPoolExecutor(max_workers=int(os.getenv("SUMMARY_WORKERS", "4"))) as executor:
        while True:
            rows = fetch_unprocessed_wikipedia_pages()
            if not rows:
                print("No more rows to process.")
                break

            futures = [executor.submit(process_row, row[0]) for row in rows]

            for future in as_completed(futures):
                future.result()
            counter += len(rows)
            print(f"{counter} pages processed")

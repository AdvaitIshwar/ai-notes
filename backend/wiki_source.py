import mwclient
import mwparserfromhell
import re
import tiktoken
WIKI_SITE = "en.wikipedia.org"

SECTIONS_TO_IGNORE = [
    "See also",
    "References",
    "External links",
    "Further reading",
    "Footnotes",
    "Bibliography",
    "Sources",
    "Citations",
    "Literature",
    "Footnotes",
    "Notes and references",
    "Photo gallery",
    "Works cited",
    "Photos",
    "Gallery",
    "Notes",
    "References and sources",
    "References and notes",
]
ENCODING = "cl100k_base"

def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

class WikiSource:
    def __init__(self, category_title):
        self.category_title = category_title
        self.site = mwclient.Site(WIKI_SITE)
        self.category_page = self.site.pages[self.category_title]
        self.total_tokens = 0
    def get_category_page(self):
        return self.category_page
    
    def titles_from_category(
        self,
        category: mwclient.listing.Category,
        max_depth: int
    ) -> set[str]:
        """Return a set of page titles in a given Wiki category and its subcategories."""
        titles = set()
        for cm in category.members():
            if type(cm) == mwclient.page.Page:
                # ^type() used instead of isinstance() to catch match w/ no inheritance
                titles.add(cm.name)
            elif isinstance(cm, mwclient.listing.Category) and max_depth > 0:
                deeper_titles = self.titles_from_category(cm, max_depth=max_depth - 1)
                titles.update(deeper_titles)
        return titles
    
    def all_subsections_from_section(
        self,
        section: mwparserfromhell.wikicode.Wikicode,
        parent_titles: list[str],
        sections_to_ignore: set[str],
    ) -> list[tuple[list[str], str]]:
        """
        From a Wikipedia section, return a flattened list of all nested subsections.
        Each subsection is a tuple, where:
            - the first element is a list of parent subtitles, starting with the page title
            - the second element is the text of the subsection (but not any children)
        """
        headings = [str(h) for h in section.filter_headings()]
        title = headings[0]
        if title.strip("=" + " ") in sections_to_ignore:
            # ^wiki headings are wrapped like "== Heading =="
            return []
        titles = parent_titles + [title]
        full_text = str(section)
        section_text = full_text.split(title)[1]
        if len(headings) == 1:
            return [(titles, section_text)]
        else:
            first_subtitle = headings[1]
            section_text = section_text.split(first_subtitle)[0]
            results = [(titles, section_text)]
            for subsection in section.get_sections(levels=[len(titles) + 1]):
                results.extend(self.all_subsections_from_section(subsection, titles, sections_to_ignore))
            return results


    def all_subsections_from_title(
        self,
        title: str,
        sections_to_ignore: set[str] = SECTIONS_TO_IGNORE,
        site_name: str = WIKI_SITE,
    ) -> list[tuple[list[str], str]]:
        """From a Wikipedia page title, return a flattened list of all nested subsections.
        Each subsection is a tuple, where:
            - the first element is a list of parent subtitles, starting with the page title
            - the second element is the text of the subsection (but not any children)
        """
        site = mwclient.Site(site_name)
        page = site.pages[title]
        text = page.text()
        parsed_text = mwparserfromhell.parse(text)
        headings = [str(h) for h in parsed_text.filter_headings()]
        if headings:
            summary_text = str(parsed_text).split(headings[0])[0]
        else:
            summary_text = str(parsed_text)
        results = [([title], summary_text)]
        for subsection in parsed_text.get_sections(levels=[2]):
            results.extend(self.all_subsections_from_section(subsection, [title], sections_to_ignore))
        return results
    
    # clean text
    def clean_section(self, section: tuple[list[str], str]) -> tuple[list[str], str]:
        """
        Return a cleaned up section with:
            - <ref>xyz</ref> patterns removed
            - leading/trailing whitespace removed
        """
        titles, text = section
        text = re.sub(r"<ref.*?</ref>", "", text)
        text = text.strip()
        return (titles, text)


    # filter out short/blank sections
    def keep_section(self, section: tuple[list[str], str]) -> bool:
        """Return True if the section should be kept, False otherwise."""
        titles, text = section
        if len(text) < 16:
            return False
        else:
            return True


    def halved_by_delimiter(self, string: str, delimiter: str = "\n") -> list[str, str]:
        """Split a string in two, on a delimiter, trying to balance tokens on each side."""
        chunks = string.split(delimiter)
        if len(chunks) == 1:
            return [string, ""]  # no delimiter found
        elif len(chunks) == 2:
            return chunks  # no need to search for halfway point
        else:
            total_tokens = num_tokens_from_string(string, ENCODING)
            halfway = total_tokens // 2
            best_diff = halfway
            for i, chunk in enumerate(chunks):
                left = delimiter.join(chunks[: i + 1])
                left_tokens = num_tokens_from_string(left, ENCODING)
                diff = abs(halfway - left_tokens)
                if diff >= best_diff:
                    break
                else:
                    best_diff = diff
            left = delimiter.join(chunks[:i])
            right = delimiter.join(chunks[i:])
            return [left, right]


    def truncated_string(
        self,
        string: str,
        max_tokens: int,
        print_warning: bool = True,
    ) -> str:
        """Truncate a string to a maximum number of tokens."""
        encoding = tiktoken.get_encoding(ENCODING)
        encoded_string = encoding.encode(string)
        truncated_string = encoding.decode(encoded_string[:max_tokens])
        if print_warning and len(encoded_string) > max_tokens:
            print(f"Warning: Truncated string from {len(encoded_string)} tokens to {max_tokens} tokens.")
        return truncated_string


    def split_strings_from_subsection(
        self,
        subsection: tuple[list[str], str],
        max_tokens: int = 1000,
        max_recursion: int = 5,
    ) -> list[str]:
        """
        Split a subsection into a list of subsections, each with no more than max_tokens.
        Each subsection is a tuple of parent titles [H1, H2, ...] and text (str).
        """
        titles, text = subsection
        string = "\n\n".join(titles + [text])
        num_tokens_in_string = num_tokens_from_string(string, ENCODING)
        self.total_tokens += num_tokens_in_string
        # if length is fine, return string
        if num_tokens_in_string <= max_tokens:
            return [string]
        # if recursion hasn't found a split after X iterations, just truncate
        elif max_recursion == 0:
            return [self.truncated_string(string, max_tokens=max_tokens)]
        # otherwise, split in half and recurse
        else:
            titles, text = subsection
            for delimiter in ["\n\n", "\n", ". "]:
                left, right = self.halved_by_delimiter(text, delimiter=delimiter)
                if left == "" or right == "":
                    # if either half is empty, retry with a more fine-grained delimiter
                    continue
                else:
                    # recurse on each half
                    results = []
                    for half in [left, right]:
                        half_subsection = (titles, half)
                        half_strings = self.split_strings_from_subsection(
                            half_subsection,
                            max_tokens=max_tokens,
                            max_recursion=max_recursion - 1,
                        )
                        results.extend(half_strings)
                    return results
        # otherwise no split was found, so just truncate (should be very rare)
        return [self.truncated_string(string, max_tokens=max_tokens)]
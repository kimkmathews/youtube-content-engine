import re

class FormatCleaner:
    @staticmethod
    def clean_markdown(text: str) -> str:
        """
        Removes weird artifacts, trailing whitespaces, and standardizes newlines.
        """
        if not text:
            return ""
        
        # Standardize newlines
        text = text.replace('\r\n', '\n')
        
        # Remove trailing whitespaces on every line
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # Ensure only a maximum of two consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

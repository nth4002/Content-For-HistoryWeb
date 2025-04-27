import docx
import uuid
import time
import io
import re
import unicodedata

from bson import ObjectId
# from odfpy import opendocument, text as odf_text # Import odfpy components
# from odf import opendocument, text as odf_text
from odf import opendocument
from odf.text import P, H

# Helper function to map option letters (A, B, C, D) to JSON keys (1, 2, 3, 4)
OPTION_KEY_MAP = {
    'A': '0',
    'B': '1',
    'C': '2',
    'D': '3'
}

def finalize_and_add_question(quiz_obj, question_obj, options_text_map, correct_letter):
    """
    Helper function to process the collected question data, format options,
    and add the complete question object to the quiz's questions list.
    Called when a question block is finished.
    Uses bson.ObjectId for option IDs.
    """
    if not quiz_obj or not question_obj:
        # Nothing to finalize if we don't have a quiz or question object
        return

    # Check if we actually collected meaningful data for this question
    # (e.g., content or options)
    if not question_obj.get('content') and not options_text_map:
        # print("end")
        return # Don't add empty question blocks

    question_obj['questionId'] = ObjectId() # Generate ID for the question
    options_list = {}

    # Ensure all expected options A, B, C, D are present based on map,
    # even if text wasn't found for them in the input.
    expected_letters = ['A', 'B', 'C', 'D']

    for letter in expected_letters:
        # Get the full line text stored during parsing
        full_option_text = options_text_map.get(letter, "").strip()

        # Determine if this option is correct based on the extracted correct_letter
        is_correct = (letter == correct_letter)

        option_key = OPTION_KEY_MAP.get(letter) # Get the corresponding JSON key (1, 2, 3, 4)

        if option_key: # Make sure mapping exists
            options_list[option_key] = {
                "optionText": full_option_text,
                "isCorrect": is_correct,
                "optionId": str(ObjectId()) # Generate ObjectId for the option
            }
        else:
             print(f"Warning: No mapping found for option letter '{letter}'")

    
    options_arr = []
    for item in options_list.items():
        options_arr.append(item[1]) # tuple of (key, value)
    question_obj['options'] = options_arr

    # print(f"Adding question obj: {question_obj}")
    # Add the complete question object to the quiz's questions list
    quiz_obj['questions'].append(question_obj)


def simple_normalize(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text



def parse_quiz_lines(lines_list):
    """
    Parses a list of text lines/paragraphs containing quiz data and converts
    it into a structured format, matching the ODT example structure where
    question content is on the same line as 'Câu hỏi N:'.

    Args:
        lines_list: A list of strings, where each string is a line or paragraph
                    from the document.

    Returns:
        A list of dictionaries, each representing a complete quiz object
        in the target JSON structure.
    """
    quizzes = []
    current_quiz = None
    current_question = None
    current_options_text = {} # To store A, B, C, D full line text temporarily
    correct_answer_letter = None # To store the correct letter (A, B, C, D)
    reference_link = "" # Variable to store the reference link for the current heritage

    # Regex to find "Câu <number>:" or "Câu hỏi <number>:" at the start of the line
    # Added \s* after ^ to handle potential leading whitespace in the line itself
    # Made 'hỏi' optional `(hỏi)?`
    cau_pattern = re.compile(r'^\s*Câu\s*(hỏi)?\s*\d+\s*:')

    # No need for awaiting_question_content_line flag with this format

    for line in lines_list:
        # Apply normalization and strip whitespace from the line
        text = simple_normalize(line) # Use the simple_normalize function
        text = text.strip()

        if not text:
            # Skip empty lines
            continue

        # --- State Machine Logic based on line patterns ---

        # 1. Heritage Section
        # Must NOT be inside a question block (current_question is None) to avoid misinterpretation
        if text.startswith('Heritage:') and current_question is None:
            # Finalize the previous quiz if exists
            if current_quiz:
                 # Ensure the last question of the previous quiz is added
                 if current_question: # Check again inside the if
                    finalize_and_add_question(
                        current_quiz,
                        current_question,
                        current_options_text,
                        correct_answer_letter
                    )
                 # Reset question state for the next section
                 current_question = None
                 current_options_text = {}
                 correct_answer_letter = None
                 reference_link = "" # Reset reference link for the new heritage


            # Start a new quiz
            # Example: Heritage: Thành nhà Hồ: heritageId: 67f3edb13834bd66e6e1c678
            parts = text.split(':', 2) # Split into max 3 parts: "Heritage", " Name ", " heritageId: ID"
            heritage_name = parts[1].strip() if len(parts) > 1 else "Unknown Heritage"

            # Find heritageId part more reliably, splitting by 'heritageId:'
            # Handle potential leading/trailing spaces around the id part after splitting by ':'
            heritage_id_part = ""
            if len(parts) > 2:
                id_segment = parts[2].strip()
                id_parts = id_segment.split('heritageId:')
                if len(id_parts) > 1:
                    heritage_id_part = id_parts[1].strip() # Get the part after 'heritageId:'

            heritage_id = heritage_id_part if heritage_id_part else "unknown_id"


            current_quiz = {
                "_id": ObjectId(), # Generate a unique ObjectId for the quiz
                "heritageId": heritage_id, # Store heritageId as string
                "title": f"Kiểm tra di tích lịch sử {heritage_name}",
                "content": f"Bài kiểm tra này sẽ giúp bạn hiểu rõ hơn về {heritage_name}",
                "questions": [],
                "topPerformersLimit": 10,
                "stats": {},
                "topPerformers": [],
                "status": "INACTIVE",
                "createdAt": int(time.time()), # Unix timestamp
                "updatedAt": int(time.time())  # Unix timestamp
            }
            quizzes.append(current_quiz)
            # print(f"Debug: Started new quiz: {heritage_name} ({heritage_id})") # Optional debug
            continue # Move to the next paragraph/line

        # 2. Link (Capture the reference link)
        # Handle both spellings and store the text after the colon
        # Must also NOT be inside a question block
        if text.startswith(('Link tham khao:', 'Link tham khảo:')) and current_question is None:
             # Extract the URL part after the prefix
             link_part = text.split(':', 1)[1].strip() if ':' in text else ""
             reference_link = text # Store the extracted link text
             # print(f"Debug: Captured link: {reference_link}") # Optional debug
             continue

        # 3. Separator (Handle if present, although not in your latest sample)
        # This signals the end of a question block, potentially starting a new one soon.
        # if text.startswith('-----'):
        #      # Finalize and add the current question if one is being processed
        #      if current_quiz and current_question:
        #          finalize_and_add_question(
        #              current_quiz,
        #              current_question,
        #              current_options_text,
        #              correct_answer_letter
        #          )
        #          # Reset question state for the next potential question
        #          current_question = None
        #          current_options_text = {}
        #          correct_answer_letter = None

        #      # print("Debug: Hit separator") # Optional debug
        #      continue # Move to the next paragraph/line

        # 4. Start of a new Question Block ("Câu N:" or "Câu hỏi N:")
        # This line now CONTAINS the question content.
        if cau_pattern.match(text):
            # print(f"Debug: Starting new question block: {text}") # Optional debug

            # Finalize and add the previous question if one was being processed
            # This handles cases where the file doesn't end with a separator
            # and a new question block starts right after the previous one ends.
            if current_quiz and current_question:
                 finalize_and_add_question(
                     current_quiz,
                     current_question,
                     current_options_text,
                     correct_answer_letter
                 )
                 # Reset question state for the new question
                 current_question = None # This will be created below
                 current_options_text = {}
                 correct_answer_letter = None


            # Start a new question object dictionary
            if current_quiz is None:
                 # We found a question before a Heritage block. This is an error
                 # based on the expected structure.
                 raise ValueError("File format error: Question found before a 'Heritage:' block.")

            # Create the dictionary for the new question
            current_question = {
                "explanation": "", # Initialize explanation
                "image": "" # Always empty as per the target structure
            }

            # Extract the question content from *this* line (after the colon)
            content_part = text.split(':', 1)[1].strip() if ':' in text else ""
            current_question['content'] = content_part
            # print(f"Debug: Captured question content from same line: '{current_question['content']}'") # Optional debug


            # No need to set awaiting_question_content_line as content is on this line

            continue # Move to the next line, expecting options


        # --- Now, process lines that are part of a question block (current_question is not None) ---
        # These checks should only run IF we have an active current_question
        if current_question is not None:

            # 5. Options Text (A., B., C., D.)
            # Must start with A., B., C., or D.
            # Store the ENTIRE line here, not just the text after the dot
            if text.startswith(('A.', 'B.', 'C.', 'D.')):
                parts = text.split('.', 1) # Split only on the first dot to get the letter
                if len(parts) >= 1: # Should always be at least 1 part if it starts with Letter.
                    option_letter = parts[0].strip() # Get the letter (e.g., "A")
                    if option_letter in ['A', 'B', 'C', 'D']:
                       # Store the full stripped line text
                       current_options_text[option_letter] = text.strip()
                       # print(f"Debug: Captured option {option_letter}: '{text}'") # Optional debug
                    else:
                       print(f"Warning: Found line starting with '{option_letter}.' not A, B, C, or D within question block: '{text}'")
                continue # Move to the next line

            # 6. Correct Answer
            # Must start with "Dap an dung:" or "Đáp án đúng:"
            elif text.startswith(('Dap an dung:', 'Đáp án đúng:')):
                # Example: "Đáp án đúng: B. Năm 1397"
                # Extract the part after the label
                answer_part = text.split(':', 1)[1].strip() if ':' in text else text.strip()

                # Find the first letter (A, B, C, or D) in the extracted part
                # This handles formats like "B. Năm 1397" or just "B"
                # Use ^[A-D] to match only if it starts with the letter after the colon and space
                match = re.search(r'^[A-D]', answer_part)
                if match:
                    correct_answer_letter = match.group(0) # Store the found letter
                    # print(f"Debug: Captured correct answer letter: {correct_answer_letter}") # Optional debug
                else:
                     # Handle case where correct answer format is unexpected
                     print(f"Warning: Could not extract correct answer letter from '{text}'. Setting correct_answer_letter to None.")
                     correct_answer_letter = None # Set to None if not found

                continue # Move to the next line

            # 7. Explanation
            # Must start with "Giai thich:" or "Giải thích:"
            elif text.startswith(('Giai thich:', 'Giải thích:')):
                 explanation_text = text.split(':', 1)[1].strip() if ':' in text else ""
                 # Append the reference link if one was captured for this heritage
                 if reference_link:
                     # Append the link text itself as requested
                     current_question['explanation'] = explanation_text + " " + reference_link
                 else:
                     current_question['explanation'] = explanation_text
                 # print(f"Debug: Captured explanation: '{current_question['explanation']}'") # Optional debug

                 # After explanation, we assume the question block is finished (unless separator follows).
                 # The logic handles this by finishing the question when the next "Câu hỏi N:" or "-----" is met.
                 # However, if a document ends right after an explanation, we need the finalization after the loop.

                 continue # Move to the next line

            # If a line is within a question block and current_question is not None,
            # AND it didn't match any specific pattern (Option, Answer, Explanation),
            # it's likely unexpected formatting or stray text. We ignore it.
            # print(f"Debug: Ignoring unhandled line within question context: '{text}'")


    # --- After the loop finishes, finalize the very last question ---
    # This is necessary if the file doesn't end with a separator or new Heritage block
    if current_quiz and current_question:
         finalize_and_add_question(
            quiz_obj=current_quiz,
            question_obj=current_question,
            options_text_map=current_options_text,
            correct_letter=correct_answer_letter
         )

    return quizzes

# --- File Reading Functions ---

def read_docx_file(docx_file_bytes: bytes) -> list[str]:
    """Reads a docx file and returns a list of paragraph texts."""
    try:
        document = docx.Document(io.BytesIO(docx_file_bytes))
        return [paragraph.text for paragraph in document.paragraphs]
    except Exception as e:
        raise ValueError(f"Error reading DOCX file: {e}")


def extract_text_recursive(element):
    """Recursively extracts all text from an ODF element and its children."""
    texts = []
    if hasattr(element, 'data') and element.data:
        texts.append(element.data)
    for child in getattr(element, 'childNodes', []):
        texts.append(extract_text_recursive(child))
    return ''.join(texts)

def read_odt_file(odt_file_bytes: bytes) -> list[str]:
    """Reads an ODT file and returns a list of text contents from paragraphs and headings."""
    lines = []
    try:
        document = opendocument.load(io.BytesIO(odt_file_bytes))
        for element in document.text.childNodes:
            if hasattr(element, 'tagName') and element.tagName in ('text:p', 'text:h'):
                paragraph_text = extract_text_recursive(element).strip()
                if paragraph_text:
                    lines.append(paragraph_text)
    except Exception as e:
        raise ValueError(f"Error reading ODT file: {e}")
    return lines


def read_txt_file(txt_file_bytes: bytes) -> list[str]:
    """Reads a txt file and returns a list of lines."""
    try:
        # Attempt to decode as UTF-8 first, as it's most common
        content = txt_file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        # Fallback to a common Western encoding if UTF-8 fails
        try:
            content = txt_file_bytes.decode('latin-1')
        except Exception as e:
            raise ValueError(f"Error decoding TXT file: {e}")

    # Split content into lines, keeping line breaks might be useful or not,
    # strip() later handles leading/trailing whitespace. splitlines() is good.
    return content.splitlines()

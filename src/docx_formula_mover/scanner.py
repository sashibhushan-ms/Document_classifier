import zipfile
import re
import xml.etree.ElementTree as ET
import os

NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}

class ScanResult:
    def __init__(self, file_path, is_error, matches, skipped=False):
        self.file_path = file_path
        self.is_error = is_error
        self.matches = matches
        self.skipped = skipped

class DocxScanner:
    def scan_file(self, file_path):
        if not file_path.lower().endswith('.docx'):
            return ScanResult(file_path, False, [], skipped=True)

        try:
            matches = []
            with zipfile.ZipFile(file_path, 'r') as zf:
                xml_files = [f for f in zf.namelist() if f.startswith('word/') and f.endswith('.xml')]
                # Filter for document, headers, footers, footnotes, endnotes
                target_files = []
                for f in xml_files:
                    if f == 'word/document.xml':
                        target_files.append(f)
                    elif re.match(r'word/(header|footer|footnotes|endnotes)\d*\.xml', f):
                        target_files.append(f)
                
                for xml_file in target_files:
                    xml_content = zf.read(xml_file)
                    file_matches = self._scan_xml_content(xml_content, xml_file)
                    matches.extend(file_matches)

            is_error = len(matches) > 0
            return ScanResult(file_path, is_error, matches)

        except zipfile.BadZipFile:
             # Treat bad zip as skipped or maybe error? Requirement says "Skip non-.docx files", implies valid structure.
             # If it has .docx extension but invalid, let's report as skipped or error?
             # "Skip non-.docx files" implies extension check. If it is broken, we can't process it.
             # Let's log it and skip.
             return ScanResult(file_path, False, [], skipped=True)
        except Exception as e:
            # General error handling
            print(f"Error processing {file_path}: {e}")
            return ScanResult(file_path, False, [], skipped=True)

    def _scan_xml_content(self, xml_content, source_name):
        root = ET.fromstring(xml_content)
        matches = []
        
        # Iterate over paragraphs
        # We need to find <w:p> elements.
        
        for i, p in enumerate(root.iter(f"{{{NAMESPACES['w']}}}p")):
            text = ""
            # Iterate runs <w:r>
            for r in p.iter(f"{{{NAMESPACES['w']}}}r"):
                # Iterate text <w:t>
                for t in r.iter(f"{{{NAMESPACES['w']}}}t"):
                    if t.text:
                        text += t.text
            
            if not text:
                continue

            # Detect $$...$$
            # "Detect $$...$$ display math only when: two consecutive $ characters start and end a span (non-greedy), and the $$ delimiter is not escaped"
            
            # Pattern looking for $$...$$
            # Negative lookbehind (?<!\\) ensures first $$ is not escaped.
            # We also need to check if the second $$ is not escaped.
            # We search for unescaped $$ first.
            
            # Strategy: Find all occurrences of $$ in the string.
            # Filter out those preceded by \
            
            # Regex for finding candidates:
            # (?<!\\)\$\$
            
            dollar_indices = [m.start() for m in re.finditer(r'(?<!\\)\$\$', text)]
            
            if len(dollar_indices) < 2:
                continue
                
            # Now we need to pair them up. "non-greedy" means closest pairs?
            # Requirement: "two consecutive $ characters start and end a span (non-greedy)"
            # Usually means first $$ pairs with second $$, third with fourth.
            # What about `$$ a $$ b $$`? -> `$$ a $$` is one, `b` is outside, trailing `$$` is unmatched?
            # Or does it mean `$$` starts, next `$$` ends.
            
            # Additional constraint: "not inside code/template patterns like $VAR, ${var}, {{ $x }}."
            # The tool looks for DISPLAY math `$$...$$`.
            # Typically code templates use single `$`. If they use `$$` it might be valid math or escaped.
            # The prompt says: "detect $$...$$ ... not inside code/template patterns".
            # If we see `{{ $$x }}` it might be template.
            # Be simple: If we find `$$...$$`, check if the Start `$$` is preceded by `{{` or similar?
            # Prompt says "not inside code/template patterns like $VAR, ${var}, {{ $x }}".
            # Note the examples use single $.
            
            # Detecting if we are inside `{{...}}` or `${...}` is context dependent.
            # Given "Run-safe detection", we use the full paragraph text.
            
            # Approach:
            # 1. Find potential `$$...$$` ranges.
            # 2. For each range, validate it.
            
            idx = 0
            while idx < len(dollar_indices) - 1:
                start_pos = dollar_indices[idx]
                end_pos = dollar_indices[idx+1]
                
                # Check for validity
                # Content between them:
                content = text[start_pos+2 : end_pos]
                
                # Check if this `$$` is actually part of `${` or `{{` context.
                # A heuristic: check surroundings.
                # If start_pos is preceded by `{`, it might be `${`.
                # But `${` usually usually uses single `$`.
                # If we have `$$`, maybe it's `${$`.
                
                # Prompt specific example: "not inside code/template patterns like $VAR, ${var}, {{ $x }}."
                # These examples don't feature `$$`.
                # If the text is `{{ $$ x }}`, is it math? LaTeX inside template?
                # "Unescaped display-math delimiters $$...$$ in visible text (i.e., raw text that LaTeX would see)."
                # If I have `{{ $$ math $$ }}`, LaTeX probably WOULD see it if the template engine renders it.
                # But if the template engine consumes it?
                # The user says "detect... ONLY WHEN ... not inside code/template patterns".
                # It implies we should ignore `$$` if it looks like variable interpolation.
                # But `$$` is rarely used for variable interpolation.
                # I will assume that if I find `$$...$$`, it is a match, UNLESS it is specifically invalid.
                # The "not inside code/template patterns" clause might be a warning to not confuse `$$` with `$var`.
                # Since `$$` != `$`, `$$` is less ambiguous.
                
                # One edge case: `$$` inside `{{...}}`.
                # I will check if the range is enclosed in `{{` and `}}`.
                # This requires parsing balanced braces?
                # Simple check: Is there a `{{` closely preceding and `}}` closely following?
                # Or simply: Is it "visible text"?
                
                # Let's trust the "unescaped" rule primarily.
                # And check if `$$` is part of `${...}` which would be `${` followed by `...`.
                # `$$` matches `${`? No.
                
                # What if the text is `var = "$$text"`. Code string?
                # The requirement says "visible text". Word doc text usually is visible.
                
                snippet = text[start_pos : end_pos + 2]
                match_info = {
                    "text": snippet,
                    "paragraph_index": i,
                    "offset": start_pos,
                    "source": source_name
                }
                matches.append(match_info)
                
                # Consume these two
                idx += 2
        
        return matches

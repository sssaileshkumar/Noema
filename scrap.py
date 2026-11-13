
import requests
import fitz
import re
import csv

PDF_URL = "https://www.dsce.edu.in/images/Pdf/TT/UG/II_Year.pdf"

START = 1
END = 120

print("Downloading DSCE student registration PDF...")

response = requests.get(
    PDF_URL,
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=60
)
response.raise_for_status()

pdf = fitz.open(
    stream=response.content,
    filetype="pdf"
)

# Match the name between CG 2 and the USN
pattern = re.compile(
    r"\bCG\s+2\s+(.+?)\s+(1DS22CG\d{3})\b",
    re.IGNORECASE
)

students = {}

for page_index, page in enumerate(pdf):

    text = page.get_text("text")

    # Normalize whitespace, including line breaks
    text = re.sub(r"\s+", " ", text)

    for match in pattern.finditer(text):

        name = match.group(1).strip()
        usn = match.group(2).upper()

        number = int(usn[-3:])

        if START <= number <= END:

            students[usn] = {
                "USN": usn,
                "Student_Name": name,
                "Page": page_index + 1,
                "PDF": PDF_URL
            }

pdf.close()

# Export all 120 USNs
output = "DSCE_CG_Students.csv"

with open(output, "w", newline="", encoding="utf-8-sig") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=[
            "USN",
            "Student_Name",
            "Page",
            "PDF"
        ]
    )

    writer.writeheader()

    for i in range(START, END + 1):

        usn = f"1DS22CG{i:03d}"

        if usn in students:
            writer.writerow(students[usn])
            print(usn, "->", students[usn]["Student_Name"])

        else:
            writer.writerow({
                "USN": usn,
                "Student_Name": "NOT FOUND IN PDF",
                "Page": "",
                "PDF": PDF_URL
            })

            print(usn, "-> NOT FOUND")

print("\n========== COMPLETE ==========")
print("Total USNs:", END - START + 1)
print("Names extracted:", len(students))
print("Not found:", END - START + 1 - len(students))
print("Output:", output)
print("==============================")

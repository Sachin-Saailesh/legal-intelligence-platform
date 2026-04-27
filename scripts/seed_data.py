#!/usr/bin/env python3
"""Seed sample legal documents and user accounts for local testing."""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


SAMPLE_CONTRACT = """SOFTWARE LICENSE AGREEMENT

This Software License Agreement ("Agreement") is entered into as of January 1, 2024,
between Acme Corporation, a Delaware corporation ("Licensor"), and Beta Inc. ("Licensee").

ARTICLE 1. DEFINITIONS

1.1 "Software" means the LexMind AI platform and all associated documentation.
1.2 "License Fee" means the monthly subscription fee of $10,000 USD.
1.3 "Confidential Information" means any non-public information disclosed by either party.

ARTICLE 2. LICENSE GRANT

2.1 Subject to the terms of this Agreement and payment of the License Fee,
Licensor hereby grants Licensee a non-exclusive, non-transferable license
to use the Software solely for Licensee's internal business purposes.

2.2 Licensee shall not sublicense, sell, resell, transfer, assign, or otherwise
dispose of the Software or Licensee's rights therein.

ARTICLE 3. PAYMENT TERMS

3.1 Licensee shall pay the License Fee on or before the first day of each calendar month.
3.2 Late payments shall accrue interest at 1.5% per month.
3.3 Licensor may suspend access upon 5 days written notice of non-payment.

ARTICLE 4. CONFIDENTIALITY

4.1 Each party agrees to keep confidential all Confidential Information received from
the other party and to use it solely in connection with this Agreement.
4.2 These obligations survive termination for a period of three (3) years.

ARTICLE 5. INDEMNIFICATION

5.1 Licensee shall defend, indemnify and hold harmless Licensor and its officers,
directors, employees and agents from any claims, damages, losses and expenses
(including reasonable attorneys' fees) arising out of or related to:
(a) Licensee's use of the Software;
(b) Licensee's breach of this Agreement;
(c) Licensee's violation of any applicable law.

5.2 Licensor shall indemnify Licensee against claims that the Software infringes
any third-party intellectual property rights.

ARTICLE 6. LIMITATION OF LIABILITY

6.1 IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES.

6.2 LICENSOR'S TOTAL LIABILITY SHALL NOT EXCEED THE FEES PAID IN THE
PRECEDING 12 MONTHS.

ARTICLE 7. TERM AND TERMINATION

7.1 This Agreement commences on the Effective Date and continues for one (1) year,
automatically renewing for successive one-year terms unless either party provides
90 days written notice of non-renewal.

7.2 Either party may terminate for material breach upon 30 days written notice
if the breach is not cured within such period.

ARTICLE 8. GOVERNING LAW

8.1 This Agreement shall be governed by the laws of the State of Delaware,
without regard to its conflict of law provisions.

8.2 Any disputes shall be resolved by binding arbitration in Wilmington, Delaware.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first written above.

ACME CORPORATION                    BETA INC.
By: John Smith                      By: Jane Doe
Title: CEO                          Title: CTO
"""

SAMPLE_CASE_LAW = """UNITED STATES DISTRICT COURT
DISTRICT OF DELAWARE

SMITH TECHNOLOGIES INC.,
    Plaintiff,
v.
JONES SOFTWARE LLC,
    Defendant.

Civil Action No. 24-cv-1234

MEMORANDUM OPINION ON MOTION FOR SUMMARY JUDGMENT

Before the Court is Defendant's Motion for Summary Judgment on the breach of contract claim.

BACKGROUND

Plaintiff entered into a software license agreement with Defendant in January 2023.
The agreement contained an indemnification clause requiring each party to defend the other
against third-party intellectual property claims.

HOLDING

The Court holds that the indemnification clause was triggered when a third party filed
suit against Plaintiff alleging that Defendant's software infringed its patents.
Under Delaware law, indemnification obligations are construed narrowly and the indemnitee
must show that the claim falls within the scope of the indemnification provision.

The Court finds that the IP infringement claim falls squarely within Article 5.2 of
the Agreement, which covers "claims that the Software infringes any third-party
intellectual property rights."

Defendant's motion for summary judgment is DENIED.

Key Holding: Indemnification clauses in software license agreements under Delaware law
must be triggered by claims that fall within the explicit scope of the indemnification
provision. Broad language such as "any third-party intellectual property rights" encompasses
patent infringement claims even when the agreement does not specifically mention patents.

Citation: Smith Technologies Inc. v. Jones Software LLC, 24-cv-1234 (D. Del. 2024)
"""


async def seed():
    from db.session import AsyncSessionFactory, engine
    from db.models import Base, Firm, User, Matter, Document, IngestionStatus
    from api.dependencies import hash_password
    import os

    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionFactory() as db:
        # Create firm and admin user
        firm_id = uuid.uuid4()
        user_id = uuid.uuid4()

        firm = Firm(id=firm_id, name="Acme Law Partners LLP", subscription_tier="professional")
        db.add(firm)

        user = User(
            id=user_id,
            email="attorney@acmelaw.com",
            hashed_password=hash_password("lexmind123"),
            role="admin",
            firm_id=firm_id,
        )
        db.add(user)
        await db.flush()

        # Create a matter
        matter_id = uuid.uuid4()
        matter = Matter(
            id=matter_id,
            firm_id=firm_id,
            title="Acme Corp Software License Agreement Review",
            matter_type="contract",
            status="active",
            jurisdiction="Delaware",
            practice_area="Corporate / M&A",
            industry="Technology",
        )
        db.add(matter)
        await db.flush()

        # Save sample documents to disk
        upload_dir = os.environ.get("UPLOAD_DIR", "/app/uploads")
        matter_dir = os.path.join(upload_dir, str(matter_id))
        os.makedirs(matter_dir, exist_ok=True)

        contract_path = os.path.join(matter_dir, "sample_license_agreement.txt")
        with open(contract_path, "w") as f:
            f.write(SAMPLE_CONTRACT)

        doc1 = Document(
            id=uuid.uuid4(),
            matter_id=matter_id,
            filename="sample_license_agreement.txt",
            file_path=contract_path,
            doc_type="contract",
            ingestion_status=IngestionStatus.pending,
        )
        db.add(doc1)

        # Create case law matter
        caselaw_matter_id = uuid.uuid4()
        caselaw_matter = Matter(
            id=caselaw_matter_id,
            firm_id=firm_id,
            title="Case Law Database",
            matter_type="litigation",
            status="active",
            jurisdiction="US Federal",
        )
        db.add(caselaw_matter)
        await db.flush()

        caselaw_path = os.path.join(matter_dir, "sample_case_law.txt")
        with open(caselaw_path, "w") as f:
            f.write(SAMPLE_CASE_LAW)

        doc2 = Document(
            id=uuid.uuid4(),
            matter_id=caselaw_matter_id,
            filename="sample_case_law.txt",
            file_path=caselaw_path,
            doc_type="case_law",
            ingestion_status=IngestionStatus.pending,
        )
        db.add(doc2)

        await db.commit()

        print(f"\n✓ Seeded successfully!")
        print(f"  Firm ID:    {firm_id}")
        print(f"  User:       attorney@acmelaw.com / lexmind123")
        print(f"  Matter ID:  {matter_id}")
        print(f"  Contract:   {contract_path}")
        print(f"\nNext: Trigger ingestion via API or:")
        print(f"  curl -X POST http://localhost:8000/api/matters/{matter_id}/documents \\")
        print(f"    -H 'Authorization: Bearer <token>' \\")
        print(f"    -F 'file=@{contract_path}'")


if __name__ == "__main__":
    asyncio.run(seed())

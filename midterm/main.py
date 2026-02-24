from fastapi import FastAPI, HTTPException, Query
from sqlmodel import Session, select
from database import engine, init_db
from model import *
import uvicorn
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # รันตอน startup ทุกครั้งที่ server เริ่ม
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        existing_data = session.exec(select(PartiesDB)).first()
        if not existing_data:
            create_election_data(session)
            print("✅ Inserted election data successfully!")
        else:
            print("ℹ️ Data already exists, skipping seed.")
    
    insert_voters() 

    yield  

app = FastAPI(lifespan=lifespan) 

RUN_SEED_DATA = True

#(1)
#insert ข้อมูลลงในตารางต่างๆ (Regions, Constituencies, Parties, Candidates)
def create_election_data(session: Session):
    # 1. Region
    region = RegionsDB(name_th="ภาคกลาง", total_population=100000)
    session.add(region)
    session.commit()
    session.refresh(region)

    # 2. Constituencies — 2 เขต
    const1 = ConstituenciesDB(region_id=region.region_id, const_number=1, total_eligible_voters=50000)
    const2 = ConstituenciesDB(region_id=region.region_id, const_number=2, total_eligible_voters=48000)
    session.add_all([const1, const2])
    session.commit()
    session.refresh(const1)
    session.refresh(const2)

    # 3. Parties — 3 พรรค
    party_a = PartiesDB(party_name="พรรคนี้เหงาจัง", party_leader="นายสมชาย", party_logo_url="url1")
    party_b = PartiesDB(party_name="พรรคพัก",        party_leader="นางสมหญิง", party_logo_url="url2")
    party_c = PartiesDB(party_name="พรรคจ้า",        party_leader="นายเก่ง",   party_logo_url="url3")
    session.add_all([party_a, party_b, party_c])
    session.commit()
    session.refresh(party_a)
    session.refresh(party_b)
    session.refresh(party_c)

    # 4. Candidates — เขตละ 3 พรรค พรรคละ 1 สส. 
    #2 เขต, เขตละ 3 พรรค, เขตละ 3 สส. รวม 6 candidates
    candidates = [
        # เขต 1
        CandidatesDB(const_id=const1.const_id, party_id=party_a.party_id, candidate_number="1", full_name="นายแดง เขต1"),
        CandidatesDB(const_id=const1.const_id, party_id=party_b.party_id, candidate_number="2", full_name="นางน้ำ เขต1"),
        CandidatesDB(const_id=const1.const_id, party_id=party_c.party_id, candidate_number="3", full_name="นายดำ เขต1"),
        # เขต 2
        CandidatesDB(const_id=const2.const_id, party_id=party_a.party_id, candidate_number="1", full_name="นายต้ม เขต2"),
        CandidatesDB(const_id=const2.const_id, party_id=party_b.party_id, candidate_number="2", full_name="นางมี เขต2"),
        CandidatesDB(const_id=const2.const_id, party_id=party_c.party_id, candidate_number="3", full_name="นายมี เขต2"),
    ]
    session.add_all(candidates)
    session.commit()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
   
@app.post("/parties/")
def create_party(party: Parties) -> PartiesOut:
    with Session(engine) as session:
        # ตรวจสอบว่าชื่อพรรคซ้ำไหม
        existing = session.exec(
            select(PartiesDB).where(PartiesDB.party_name == party.party_name)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="ชื่อพรรคนี้มีอยู่แล้ว")

        db_party = PartiesDB(**party.model_dump())
        session.add(db_party)
        session.commit()
        session.refresh(db_party)
        return db_party
    
@app.post("/candidates/")
def create_candidate(candidate: Candidates) -> CandidateFullOut:
    with Session(engine) as session:
        # ตรวจสอบว่า const_id มีอยู่จริง
        const_db = session.get(ConstituenciesDB, candidate.const_id)
        if not const_db:
            raise HTTPException(status_code=404, detail=f"ไม่พบเขตเลือกตั้ง const_id={candidate.const_id}")

        # ตรวจสอบว่า party_id มีอยู่จริง
        party_db = session.get(PartiesDB, candidate.party_id)
        if not party_db:
            raise HTTPException(status_code=404, detail=f"ไม่พบพรรค party_id={candidate.party_id}")

        # ตรวจสอบว่าพรรคนี้ส่งผู้สมัครในเขตนี้ไปแล้วหรือยัง
        duplicate = session.exec(
            select(CandidatesDB).where(
                CandidatesDB.const_id == candidate.const_id,
                CandidatesDB.party_id == candidate.party_id,
            )
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="พรรคนี้มีผู้สมัครในเขตนี้แล้ว")

        db_candidate = CandidatesDB(**candidate.model_dump())
        session.add(db_candidate)
        session.commit()
        session.refresh(db_candidate)

        # Return พร้อม nested party + constituency
        return CandidateFullOut(
            candidate_id=db_candidate.candidate_id,
            candidate_number=int(db_candidate.candidate_number),
            full_name=db_candidate.full_name,
            party=PartyFullOut(
                party_id=party_db.party_id,
                party_name=party_db.party_name,
                party_leader=party_db.party_leader,
                party_logo_url=party_db.party_logo_url,
            ),
            constituency=ConstituencyFullOut(
                const_id=const_db.const_id,
                const_number=const_db.const_number,
                total_eligible_voters=const_db.total_eligible_voters,
                region_id=const_db.region_id,
            ),
        )


#get all รายชื่อพรรคการเมือง ผู้สมัครสสเขต & รายละเอียดเขตเลือกตั้ง
@app.get("/overview/")
def get_overview() -> List[PartyOverviewOut]:
    with Session(engine) as session:
        stmt = (
            select(PartiesDB, CandidatesDB, ConstituenciesDB, RegionsDB)
            .where(PartiesDB.party_id == CandidatesDB.party_id)
            .where(CandidatesDB.const_id == ConstituenciesDB.const_id)
            .where(ConstituenciesDB.region_id == RegionsDB.region_id)
            .order_by(PartiesDB.party_id, ConstituenciesDB.const_number)
        )
        rows = session.exec(stmt).all()
        print(f"rows after where: {len(rows)}")
        #where แทน join
        stmt = (
            select(PartiesDB, CandidatesDB, ConstituenciesDB, RegionsDB)
            .where(PartiesDB.party_id == CandidatesDB.party_id)
            .where(CandidatesDB.const_id == ConstituenciesDB.const_id)
            .where(ConstituenciesDB.region_id == RegionsDB.region_id)
            .order_by(PartiesDB.party_id, ConstituenciesDB.const_number)
        )
        rows = session.exec(stmt).all()

        #จัดกลุ่มเหมือนเดิม
        party_map: dict[int, PartyOverviewOut] = {}

        for party, cand, const_, region in rows:

            if party.party_id not in party_map:
                party_map[party.party_id] = PartyOverviewOut(
                    party_id=party.party_id,
                    party_name=party.party_name,
                    party_leader=party.party_leader,
                    party_logo_url=party.party_logo_url,
                    total_candidates=0,
                )

            party_entry = party_map[party.party_id]

            const_entry = next(
                (c for c in party_entry.constituencies if c.const_id == const_.const_id),
                None
            )
            if const_entry is None:
                const_entry = ConstituencyBriefOut(
                    const_id=const_.const_id,
                    const_number=const_.const_number,
                    region_name=region.name_th,
                    total_eligible_voters=const_.total_eligible_voters,
                )
                party_entry.constituencies.append(const_entry)

            const_entry.candidates.append(
                CandidateBriefOut(
                    candidate_id=cand.candidate_id,
                    candidate_number=int(cand.candidate_number),
                    full_name=cand.full_name,
                )
            )
            party_entry.total_candidates += 1

        return list(party_map.values())

##(2)voters 
def insert_voters():
    # เตรียมข้อมูล 20 รายชื่อ (ตัวอย่าง)
    voters_list = [
        VotersDB(citizen_id=1100100000001, full_name="นายสมชาย รักชาติ", const_id=1),
        VotersDB(citizen_id=1100100000002, full_name="นางสาวสมหญิง ยิ่งรวย", const_id=1),
        VotersDB(citizen_id=1100100000003, full_name="นายมานะ อดทน", const_id=1),
        VotersDB(citizen_id=1100100000004, full_name="นางปิติ ยินดี", const_id=1),
        VotersDB(citizen_id=1100100000005, full_name="นายชูใจ ใฝ่เรียน", const_id=1),
        VotersDB(citizen_id=1100100000006, full_name="นายวีระ กล้าหาญ", const_id=1),
        VotersDB(citizen_id=1100100000007, full_name="นายดวงดี มีทรัพย์", const_id=1),
        VotersDB(citizen_id=1100100000008, full_name="นางนารี รุ่งเรือง", const_id=1),
        VotersDB(citizen_id=1100100000009, full_name="นายบุญส่ง เสริมศรี", const_id=1),
        VotersDB(citizen_id=1100100000010, full_name="นางสาวสายใจ รักสงบ", const_id=1),
        VotersDB(citizen_id=2200200000001, full_name="นายวิชัย ชนะศึก", const_id=2),
        VotersDB(citizen_id=2200200000002, full_name="นางกนกพร พรหมมา", const_id=2),
        VotersDB(citizen_id=2200200000003, full_name="นายธวัชชัย สายเสมอ", const_id=2),
        VotersDB(citizen_id=2200200000004, full_name="นางสาวเบญจมาศ สวยงาม", const_id=2),
        VotersDB(citizen_id=2200200000005, full_name="นายปกรณ์ ปราชญ์ดี", const_id=2),
        VotersDB(citizen_id=2200200000006, full_name="นางราตรี มืดมิด", const_id=2),
        VotersDB(citizen_id=2200200000007, full_name="นายอาทิตย์ สว่างไสว", const_id=2),
        VotersDB(citizen_id=2200200000008, full_name="นางสาวศิริพร เพ็ญศรี", const_id=2),
        VotersDB(citizen_id=2200200000009, full_name="นายเอกราช ชาติไทย", const_id=2),
        VotersDB(citizen_id=2200200000010, full_name="นางจรุงใจ จิตตรง", const_id=2)
    ]

    with Session(engine) as s:
        existing = s.exec(select(VotersDB)).first()
        if not existing:
            for voter in voters_list:
                s.add(voter)
            s.commit()
            print("✅ Inserted 20 voters successfully!")
        else:
            print("ℹ️ Voters already exist, skipping insert.")

    #seed votes หลัง insert voters เสร็จ
    insert_votes()

def insert_votes():
    # เขต 1: candidate 1,2,3 | เขต 2: candidate 4,5,6
    # party 1,2,3
    votes = [
        # ─── เขต 1 (citizen 001-010) ───────────────────────────
        #โหวตทั้งคู๋
        (1100100000001, "constituency", 1, None),
        (1100100000001, "party-list",   None, 1),

        (1100100000002, "constituency", 2, None),
        (1100100000002, "party-list",   None, 2),

        (1100100000003, "constituency", 3, None),
        (1100100000003, "party-list",   None, 3),

        (1100100000004, "constituency", 1, None),
        (1100100000004, "party-list",   None, 1),

        (1100100000005, "constituency", 2, None),
        (1100100000005, "party-list",   None, 2),

        #โหวตเขตอย่างเดียว
        (1100100000006, "constituency", 3, None),

        #โหวตบัญชีรายชื่ออย่างเดียว
        (1100100000007, "party-list", None, 3),
        (1100100000008, "party-list", None, 1),

        #ไม่โหวตเลย: 009, 010

        # ─── เขต 2 (citizen 001-010) ───────────────────────────
        #โหวตทั้งคู่
        (2200200000001, "constituency", 4, None),
        (2200200000001, "party-list",   None, 1),

        (2200200000002, "constituency", 5, None),
        (2200200000002, "party-list",   None, 2),

        (2200200000003, "constituency", 6, None),
        (2200200000003, "party-list",   None, 3),

        (2200200000004, "constituency", 4, None),
        (2200200000004, "party-list",   None, 2),

        (2200200000005, "constituency", 5, None),
        (2200200000005, "party-list",   None, 1),

        #โหวตเขตอย่างเดียว
        (2200200000006, "constituency", 6, None),

        #โหวตบัญชีรายชื่ออย่างเดียว
        (2200200000007, "party-list", None, 3),
        (2200200000008, "party-list", None, 2),

        #ไม่โหวตเลย: 009, 010
    ]

    with Session(engine) as s:
        existing = s.exec(select(BallotsDB)).first()
        if existing:
            print("ℹ️ Votes already exist, skipping insert.")
            return

        for citizen_id, vote_type, candidate_id, party_id in votes:
            voter = s.exec(
                select(VotersDB).where(VotersDB.citizen_id == citizen_id)
            ).first()
            if not voter:
                continue

            ballot = BallotsDB(
                const_id=voter.const_id,
                candidate_id=candidate_id,
                party_id=party_id,
                vote_type=vote_type,
            )
            s.add(ballot)

            #อัพเดต has_voted
            if vote_type == "constituency":
                voter.has_voted_const = 1
            elif vote_type == "party-list":
                voter.has_voted_list = 1
            s.add(voter)

        s.commit()
        print("✅ Inserted votes successfully!")
    

#  สร้างผู้มีสิทธิเลือกตั้งใหม่
@app.post("/voters/")
async def create_voter(voter: Voters) -> VotersOut: 
    with Session(engine) as session:
        #ตรวจสอบว่าเลขบัตรประชาชนซ้ำไหม 
        statement = select(VotersDB).where(VotersDB.citizen_id == voter.citizen_id)
        existing = session.exec(statement).first()
        if existing:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="เลขบัตรประชาชนนี้มีในระบบแล้ว")

        #สร้าง Object ใหม่โดยใช้ข้อมูลจาก request body
        #voter_id เป็น null เพื่อให้ DB รันเลขให้อัตโนมัติ
        new_voter = VotersDB(**voter.model_dump())

        session.add(new_voter)
        session.commit()
        session.refresh(new_voter)
        
        print(f"Created Voter ID: {new_voter.voter_id}")
        return new_voter

@app.get("/voters/")
def get_voters(const_id: int = Query(None)) -> List[VotersOut]: 
    with Session(engine) as session:
        statement = select(VotersDB)
        if const_id:
            statement = statement.where(VotersDB.const_id == const_id)
        results = session.exec(statement).all()
        return results

@app.put("/voters/{voter_id}/vote")
async def cast_vote(voter_id: int, vote_type: str) -> VotersDB:
    """
    vote_type: 'const' หรือ 'list'
    """
    with Session(engine) as session:
        db_voter = session.get(VotersDB, voter_id)
        
        if not db_voter:
            raise HTTPException(status_code=404, detail="ไม่พบรายชื่อ")

        if vote_type == "const":
            db_voter.has_voted_const = 1
        elif vote_type == "list":
            db_voter.has_voted_list = 1
        
        session.add(db_voter)
        session.commit()
        session.refresh(db_voter)
        return db_voter
    
#(3) ลงคะแนนเลือกตั้ง
@app.post("/votes/")
def cast_ballot(vote: VoteRequest):
    with Session(engine) as session:

        # หา voter จาก citizen_id
        voter = session.exec(
            select(VotersDB).where(VotersDB.citizen_id == vote.voter_id)
        ).first()
        if not voter:
            raise HTTPException(status_code=404, detail="ไม่พบผู้มีสิทธิ์เลือกตั้ง")

        # เช็คตาม vote_type
        if vote.vote_type == "constituency":
            if voter.has_voted_const == 1:
                raise HTTPException(status_code=400, detail="ลงคะแนนเขตไปแล้ว")
            if not vote.candidate_id:
                raise HTTPException(status_code=400, detail="ต้องระบุ candidate_id")

            # เช็คว่า candidate อยู่ในเขตเดียวกับ voter
            candidate = session.get(CandidatesDB, vote.candidate_id)
            if not candidate:
                raise HTTPException(status_code=404, detail="ไม่พบผู้สมัคร")
            if candidate.const_id != voter.const_id:
                raise HTTPException(status_code=400, detail="ผู้สมัครไม่ได้อยู่ในเขตของคุณ")

            # บันทึก ballot
            ballot = BallotsDB(
                const_id=voter.const_id,
                candidate_id=vote.candidate_id,
                party_id=None,
                vote_type="constituency",
            )
            voter.has_voted_const = 1

        elif vote.vote_type == "party-list":
            if voter.has_voted_list == 1:
                raise HTTPException(status_code=400, detail="ลงคะแนนบัญชีรายชื่อไปแล้ว")
            if not vote.party_id:
                raise HTTPException(status_code=400, detail="ต้องระบุ party_id")

            party = session.get(PartiesDB, vote.party_id)
            if not party:
                raise HTTPException(status_code=404, detail="ไม่พบพรรค")

            ballot = BallotsDB(
                const_id=voter.const_id,
                candidate_id=None,
                party_id=vote.party_id,
                vote_type="party-list",
            )
            voter.has_voted_list = 1

        else:
            raise HTTPException(status_code=400, detail="vote_type ต้องเป็น 'constituency' หรือ 'party-list'")

        session.add(ballot)
        session.add(voter)
        session.commit()

        return {"message": "บันทึกคะแนนเรียบร้อย", "vote_type": vote.vote_type}

# ─── GET จำนวนผู้มาใช้สิทธิเลือกตั้งแยกตามเขตเลือกตั้งแบบพรรคการเมือง ──────────────

@app.get("/votes/constituency/voter-count-by-party/")
def get_voter_count_by_party() -> List[VoterCountByPartyOut]:
    with Session(engine) as session:
        rows = session.exec(
            select(ConstituenciesDB, RegionsDB)
            .where(ConstituenciesDB.region_id == RegionsDB.region_id)
            .order_by(ConstituenciesDB.const_number)
        ).all()

        results = []
        for const_, region in rows:

            # นับคนที่โหวตบัญชีรายชื่อในเขตนี้
            total_voted = len(session.exec(
                select(VotersDB)
                .where(VotersDB.const_id == const_.const_id)
                .where(VotersDB.has_voted_list == 1)
            ).all())

            turnout = round(total_voted / const_.total_eligible_voters * 100, 2) if const_.total_eligible_voters > 0 else 0.0

            # คะแนนแต่ละพรรคในเขตนี้ (จาก ballots ของ voters ในเขตนี้)
            parties = session.exec(select(PartiesDB)).all()
            party_results = []
            for party in parties:
                vote_count = len(session.exec(
                    select(BallotsDB)
                    .where(BallotsDB.vote_type == "party-list")
                    .where(BallotsDB.party_id == party.party_id)
                    .where(BallotsDB.const_id == const_.const_id)
                ).all())

                party_results.append(PartyResultOut(
                    party_id=party.party_id,
                    party_name=party.party_name,
                    party_leader=party.party_leader,
                    total_votes=vote_count,
                ))

            party_results.sort(key=lambda x: x.total_votes, reverse=True)

            results.append(VoterCountByPartyOut(
                const_id=const_.const_id,
                const_number=const_.const_number,
                region_name=region.name_th,
                total_eligible_voters=const_.total_eligible_voters,
                total_voted=total_voted,
                turnout_percent=turnout,
                parties=party_results,
            ))

        return results


# ─── GET จำนวนผู้มาใช้สิทธิเลือกตั้งแยกตามเขตเลือกตั้งแบบบัญชีรายชื่อ ────────

@app.get("/votes/constituency/voter-count-by-constituency/")
def get_voter_count_by_constituency() -> List[VoterCountByConstOut]:
    with Session(engine) as session:
        rows = session.exec(
            select(ConstituenciesDB, RegionsDB)
            .where(ConstituenciesDB.region_id == RegionsDB.region_id)
            .order_by(ConstituenciesDB.const_number)
        ).all()

        results = []
        for const_, region in rows:

            # นับคนที่โหวตเขตในเขตนี้
            total_voted = len(session.exec(
                select(VotersDB)
                .where(VotersDB.const_id == const_.const_id)
                .where(VotersDB.has_voted_const == 1)
            ).all())

            turnout = round(total_voted / const_.total_eligible_voters * 100, 2) if const_.total_eligible_voters > 0 else 0.0

            # คะแนนแต่ละผู้สมัครในเขตนี้
            candidates = session.exec(
                select(CandidatesDB).where(CandidatesDB.const_id == const_.const_id)
            ).all()

            cand_results = []
            for cand in candidates:
                party = session.get(PartiesDB, cand.party_id)
                vote_count = len(session.exec(
                    select(BallotsDB)
                    .where(BallotsDB.candidate_id == cand.candidate_id)
                    .where(BallotsDB.vote_type == "constituency")
                ).all())

                cand_results.append(CandidateInConstResult(
                    candidate_id=cand.candidate_id,
                    candidate_number=int(cand.candidate_number),
                    full_name=cand.full_name,
                    party_name=party.party_name if party else "-",
                    total_votes=vote_count,
                ))

            cand_results.sort(key=lambda x: x.total_votes, reverse=True)

            results.append(VoterCountByConstOut(
                const_id=const_.const_id,
                const_number=const_.const_number,
                region_name=region.name_th,
                total_eligible_voters=const_.total_eligible_voters,
                total_voted=total_voted,
                turnout_percent=turnout,
                candidates=cand_results,
            ))

        return results

#(4)ผลคะแนนรวม
#ผลคะแนนเลือกตั้งแบบเขต
@app.get("/votes/constituency/{const_id}/")
def get_constituency_results(const_id: int) -> List[CandidateResultOut]:
    with Session(engine) as session:

        # เช็คว่าเขตมีอยู่จริง
        const = session.get(ConstituenciesDB, const_id)
        if not const:
            raise HTTPException(status_code=404, detail="ไม่พบเขตเลือกตั้ง")

        # ดึง candidates ในเขตนี้
        candidates = session.exec(
            select(CandidatesDB).where(CandidatesDB.const_id == const_id)
        ).all()

        results = []
        for cand in candidates:
            # นับคะแนนจาก ballots
            vote_count = len(session.exec(
                select(BallotsDB).where(
                    BallotsDB.candidate_id == cand.candidate_id,
                    BallotsDB.vote_type == "constituency"
                )
            ).all())

            party = session.get(PartiesDB, cand.party_id)

            results.append(CandidateResultOut(
                candidate_id=cand.candidate_id,
                candidate_number=int(cand.candidate_number),
                full_name=cand.full_name,
                party_name=party.party_name if party else "-",
                total_votes=vote_count,
            ))

        # เรียงจากคะแนนมากไปน้อย
        results.sort(key=lambda x: x.total_votes, reverse=True)
        return results
    
#──────────────get ผลคะแนนเลือกตั้งแบบบัญชีรายชื่อ─────────────────────────────────────
@app.get("/votes/party-list/")
def get_partylist_results() -> List[PartyResultOut]:
    with Session(engine) as session:

        parties = session.exec(select(PartiesDB)).all()

        results = []
        for party in parties:
            vote_count = len(session.exec(
                select(BallotsDB).where(
                    BallotsDB.party_id == party.party_id,
                    BallotsDB.vote_type == "party-list"
                )
            ).all())

            results.append(PartyResultOut(
                party_id=party.party_id,
                party_name=party.party_name,
                party_leader=party.party_leader,
                total_votes=vote_count,
            ))

        results.sort(key=lambda x: x.total_votes, reverse=True)
        return results
    
# ─── GET แสดงผลการนับคะแนนแบบบัญชีรายชื่อ ──────────────────────────────────────────

@app.get("/votes/party/", response_model=List[PartyTotalResultOut])
def get_party_results():
    with Session(engine) as session:
        parties = session.exec(select(PartiesDB)).all()

        results = []
        for party in parties:
            # ดึง candidate_id ของพรรคนี้ก่อน
            party_candidates = session.exec(
                select(CandidatesDB).where(CandidatesDB.party_id == party.party_id)
            ).all()
            candidate_ids = [c.candidate_id for c in party_candidates]

            # นับคะแนนเขต
            const_votes = 0
            if candidate_ids:
                for cid in candidate_ids:
                    const_votes += len(session.exec(
                        select(BallotsDB)
                        .where(BallotsDB.candidate_id == cid)
                        .where(BallotsDB.vote_type == "constituency")
                    ).all())

            # นับคะแนนบัญชีรายชื่อ
            list_votes = len(session.exec(
                select(BallotsDB)
                .where(BallotsDB.party_id == party.party_id)
                .where(BallotsDB.vote_type == "party-list")
            ).all())

            results.append(PartyTotalResultOut(
                party_id=party.party_id,
                party_name=party.party_name,
                party_leader=party.party_leader,
                constituency_votes=const_votes,
                partylist_votes=list_votes,
                total_votes=const_votes + list_votes,
            ))

        results.sort(key=lambda x: x.total_votes, reverse=True)
        return results


# ─── GET แสดงผลการเลือกตั้งแบบผู้สมัครสสเขต ─────────────────────────────────────

@app.get("/votes/candidates/")
def get_candidate_results() -> List[CandidateTotalResultOut]:
    with Session(engine) as session:
        rows = session.exec(
            select(CandidatesDB, PartiesDB, ConstituenciesDB)
            .where(CandidatesDB.party_id == PartiesDB.party_id)
            .where(CandidatesDB.const_id == ConstituenciesDB.const_id)
            .order_by(ConstituenciesDB.const_number, CandidatesDB.candidate_number)
        ).all()

        results = []
        for cand, party, const_ in rows:
            vote_count = len(session.exec(
                select(BallotsDB)
                .where(BallotsDB.candidate_id == cand.candidate_id)
                .where(BallotsDB.vote_type == "constituency")
            ).all())

            results.append(CandidateTotalResultOut(
                candidate_id=cand.candidate_id,
                candidate_number=int(cand.candidate_number),
                full_name=cand.full_name,
                party_name=party.party_name,
                const_number=const_.const_number,
                total_votes=vote_count,
            ))

        results.sort(key=lambda x: x.total_votes, reverse=True)
        return results

@app.get("/votes/constituency/{const_id}/")
def get_constituency_results(const_id: int) -> List[CandidateResultOut]:
    with Session(engine) as session:
        const = session.get(ConstituenciesDB, const_id)
        if not const:
            raise HTTPException(status_code=404, detail="ไม่พบเขตเลือกตั้ง")

        candidates = session.exec(
            select(CandidatesDB).where(CandidatesDB.const_id == const_id)
        ).all()

        results = []
        for cand in candidates:
            vote_count = len(session.exec(
                select(BallotsDB).where(
                    BallotsDB.candidate_id == cand.candidate_id,
                    BallotsDB.vote_type == "constituency"
                )
            ).all())
            party = session.get(PartiesDB, cand.party_id)
            results.append(CandidateResultOut(
                candidate_id=cand.candidate_id,
                candidate_number=int(cand.candidate_number),
                full_name=cand.full_name,
                party_name=party.party_name if party else "-",
                total_votes=vote_count,
            ))

        results.sort(key=lambda x: x.total_votes, reverse=True)
        return results
from datetime import datetime
from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from typing import Optional, List

#1)ตารางจังหวัด ภูมิภาค
class Regions(BaseModel):
    name_th: str = Field(unique=True)
    total_population: int = 0

class RegionsOut(Regions):
    region_id: int

class RegionsDB(SQLModel, table=True):
    region_id: int | None = Field(default=None, primary_key=True)
    name_th: str = Field(unique=True)
    total_population: int = 0

#2)เขตเลือกตั้ง
class Constituencies(BaseModel):
    region_id: int
    const_number: int
    total_eligible_voters: int = 0

class ConstituenciesOut(Constituencies):
    const_id: int

class ConstituenciesDB(SQLModel, table=True):
    const_id: int | None = Field(default=None, primary_key=True)
    region_id: int 
    const_number: int
    total_eligible_voters: int = 0

#3)พรรคการเมือง
class Parties(BaseModel):
    party_name: str = Field(unique=True)
    party_leader: str
    party_logo_url: str

class PartiesOut(Parties):
    party_id: int

class PartiesDB(SQLModel, table=True):
    party_id: int | None = Field(default=None, primary_key=True)
    party_name: str = Field(unique=True)
    party_leader: str
    party_logo_url: str


#4 ผู้สมัครสสเขต
class Candidates(BaseModel):
    const_id: int
    party_id: int
    candidate_number: int
    full_name: str

class CandidatesOut(Candidates):
    candidate_id: int

class CandidatesDB(SQLModel, table=True):
    candidate_id: int | None = Field(default=None, primary_key=True)
    const_id: int
    party_id: int
    candidate_number: str
    full_name: str

#5 voters
class Voters(BaseModel):
    citizen_id: int = Field(unique=True)
    full_name: str
    const_id: int
    has_voted_const: int = Field(default=0, ge=0, le=1, description="0: Not Voted, 1: Voted")
    has_voted_list: int = Field(default=0, ge=0, le=1, description="0: Not Voted, 1: Voted")
    

class VotersOut(Voters):
    voter_id: int

class VotersDB(SQLModel, table=True):
    voter_id: int | None = Field(default=None, primary_key=True)
    citizen_id: int = Field(unique=True)
    full_name: str
    const_id: int
    has_voted_const: int = Field(default=0)
    has_voted_list: int = Field(default=0)

#6 ตารางบันทึกคะแนน
class Ballots(BaseModel):
    const_id: int
    candidate_id: int | None = Field(default=None, description="NULL if No Vote")
    party_id: int  | None = Field(default=None, description="NULL if No Vote")
    vote_type: str = Field(description="constituency or party-list")
    voted_at: datetime = Field(default_factory=datetime.now)

class BallotsOut(Ballots):
    ballot_id: int

class BallotsDB(SQLModel, table=True):
    ballot_id: int | None = Field(default=None, primary_key=True)
    const_id: int
    candidate_id: int | None = Field(default=None, description="NULL if No Vote")
    party_id: int  | None = Field(default=None, description="NULL if No Vote")
    vote_type: str = Field(description="constituency or party-list")
    voted_at: datetime = Field(default_factory=datetime.now)

# --- สำหรับแสดงรายละเอียดของเขตเลือกตั้งและผู้สมัครในเขตนั้น (ใช้ใน CandidateFullOut) ---
# --- รายละเอียดเขตแบบเต็ม ---
class ConstituencyFullOut(BaseModel):
    const_id: int
    const_number: int
    total_eligible_voters: int
    region_id: int

# --- 1. สำหรับพรรคการเมือง ---
class PartyFullOut(PartiesOut):
    # หากพรรคมีเขตที่สังกัด (เช่น พรรคนี้ส่ง สส. ในเขตไหนบ้าง - ถ้ามี) 
    # หรือจะแสดงข้อมูลทั่วไปของพรรคเฉยๆ ก็ได้
    pass

# --- 2. สำหรับผู้สมัคร (มีทั้งข้อมูลพรรคและเขต) ---
class CandidateFullOut(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str
    party: PartyFullOut | None = None
    constituency: ConstituencyFullOut | None = None

# สำหรับแสดง candidates ในแต่ละเขต (ใช้ใน PartyWithConstituenciesOut)
class CandidateInConstOut(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str

# เขต + รายชื่อ สส. ของพรรคในเขตนั้น
class ConstituencyWithCandidatesOut(BaseModel):
    const_id: int
    const_number: int
    total_eligible_voters: int
    region_id: int
    candidates: List[CandidateInConstOut] = []

# พรรค + เขตทั้งหมดที่พรรคส่งผู้สมัคร
class PartyWithConstituenciesOut(BaseModel):
    party_id: int
    party_name: str
    party_leader: str
    party_logo_url: str
    constituencies: List[ConstituencyWithCandidatesOut] = []

class CandidateBriefOut(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str

class ConstituencyBriefOut(BaseModel):
    const_id: int
    const_number: int
    region_name: str          # ชื่อภูมิภาค เช่น "ภาคกลาง"
    total_eligible_voters: int
    candidates: List[CandidateBriefOut] = []

class PartyOverviewOut(BaseModel):
    party_id: int
    party_name: str
    party_leader: str
    party_logo_url: str
    total_candidates: int     # รวมจำนวน สส. ทั้งหมดของพรรค
    constituencies: List[ConstituencyBriefOut] = []

#  สำหรับการลงคะแนนเสียง 
class VoteRequest(BaseModel):
    voter_id: int  # citizen_id
    vote_type: str  # "constituency" หรือ "party-list"
    candidate_id: int | None = None  # ถ้า constituency
    party_id: int | None = None      # ถ้า party-list

class CandidateResultOut(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str
    party_name: str
    total_votes: int

class PartyResultOut(BaseModel):
    party_id: int
    party_name: str
    party_leader: str
    total_votes: int

class PartyTotalResultOut(BaseModel):
    party_id: int
    party_name: str
    party_leader: str
    constituency_votes: int   # คะแนนเขต
    partylist_votes: int       # คะแนนบัญชีรายชื่อ
    total_votes: int           # รวมทั้งหมด

class CandidateTotalResultOut(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str
    party_name: str
    const_number: int
    total_votes: int

class CandidateInConstResult(BaseModel):
    candidate_id: int
    candidate_number: int
    full_name: str
    party_name: str
    total_votes: int

class ConstOverviewOut(BaseModel):
    const_id: int
    const_number: int
    region_name: str
    total_eligible_voters: int
    total_voted_const: int      # คนที่โหวตเขตแล้ว
    total_voted_partylist: int  # คนที่โหวตบัญชีแล้ว
    candidates: List[CandidateInConstResult] = []

class VoterCountByPartyOut(BaseModel):
    const_id: int
    const_number: int
    region_name: str
    total_eligible_voters: int
    total_voted: int           # คนที่โหวตบัญชีรายชื่อ
    turnout_percent: float
    parties: List[PartyResultOut] = []  # คะแนนแต่ละพรรคในเขตนี้

class VoterCountByConstOut(BaseModel):
    const_id: int
    const_number: int
    region_name: str
    total_eligible_voters: int
    total_voted: int           # คนที่โหวตเขต
    turnout_percent: float
    candidates: List[CandidateInConstResult] = []
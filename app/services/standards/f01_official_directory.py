"""팀 업무분장 PDF에 표시된 *팀장 직위* 업무 연락처(대표번호 아님).

각 기록의 source_ref는 2026-11-04 조회한 팀 공유 Drive의 성남시 조직도 업무분장 PDF.
자료의 유효기간/갱신 여부는 별도 검증이 필요하다. DB 관할 확정이나 등급 승인과 무관하다.
"""
from __future__ import annotations

OFFICIAL_TEAM_LEAD_DIRECTORY = (
    {"gu_name":'성남시', "receiving_dept":'교통기획과 교통시설팀', "dept_team":'교통시설팀', "dept_phone":'031-729-3671', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1ezOhvP0yaK0SGQQ9TUPXJuWGv8C5FITC/view"},
    {"gu_name":'성남시', "receiving_dept":'교통기획과 교통지도팀', "dept_team":'교통지도팀', "dept_phone":'031-729-3701', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1ezOhvP0yaK0SGQQ9TUPXJuWGv8C5FITC/view"},
    {"gu_name":'성남시', "receiving_dept":'도로과 도로관리팀', "dept_team":'도로관리팀', "dept_phone":'031-729-3611', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1Tct9xHf3jm6Mv9v40xMEIvVCMPerNfbF/view"},
    {"gu_name":'성남시', "receiving_dept":'도로과 도로행정팀', "dept_team":'도로행정팀', "dept_phone":'031-729-3591', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1Tct9xHf3jm6Mv9v40xMEIvVCMPerNfbF/view"},
    {"gu_name":'수정구', "receiving_dept":'건설과 도로관리팀', "dept_team":'도로관리팀', "dept_phone":'031-729-5350', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1RxXdi-t8X0LCT-Wkg5av043zPOkKgqfn/view"},
    {"gu_name":'수정구', "receiving_dept":'건설과 건설행정취락정비팀', "dept_team":'건설행정취락정비팀', "dept_phone":'031-729-5330', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1RxXdi-t8X0LCT-Wkg5av043zPOkKgqfn/view"},
    {"gu_name":'수정구', "receiving_dept":'건설과 도로조명팀', "dept_team":'도로조명팀', "dept_phone":'031-729-5460', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1RxXdi-t8X0LCT-Wkg5av043zPOkKgqfn/view"},
    {"gu_name":'수정구', "receiving_dept":'경제교통과 교통행정팀', "dept_team":'교통행정팀', "dept_phone":'031-729-5430', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1ZrxDOQ8Vb2Rjcyz7-JVONH1XW-RTh-1t/view"},
    {"gu_name":'수정구', "receiving_dept":'경제교통과 주차관리팀', "dept_team":'주차관리팀', "dept_phone":'031-729-5440', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1ZrxDOQ8Vb2Rjcyz7-JVONH1XW-RTh-1t/view"},
    {"gu_name":'중원구', "receiving_dept":'건설과 도로관리팀', "dept_team":'도로관리팀', "dept_phone":'031-729-6350', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1hepBUzBl2RAwYZXg1yJdReVE9GIph59A/view"},
    {"gu_name":'중원구', "receiving_dept":'건설과 건설행정팀', "dept_team":'건설행정팀', "dept_phone":'031-729-6330', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1hepBUzBl2RAwYZXg1yJdReVE9GIph59A/view"},
    {"gu_name":'중원구', "receiving_dept":'건설과 도로조명팀', "dept_team":'도로조명팀', "dept_phone":'031-729-6360', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1hepBUzBl2RAwYZXg1yJdReVE9GIph59A/view"},
    {"gu_name":'중원구', "receiving_dept":'경제교통과 교통행정팀', "dept_team":'교통행정팀', "dept_phone":'031-729-6430', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/11kvRc4ZMyb9OnAPzNeBPq6doYuFuss6n/view"},
    {"gu_name":'중원구', "receiving_dept":'경제교통과 주차관리팀', "dept_team":'주차관리팀', "dept_phone":'031-729-6440', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/11kvRc4ZMyb9OnAPzNeBPq6doYuFuss6n/view"},
    {"gu_name":'분당구', "receiving_dept":'건설과 도로관리팀', "dept_team":'도로관리팀', "dept_phone":'031-729-7360', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1iCcdmLBfH7HwJ_IHeDBLR1Ei55jWQQ8o/view"},
    {"gu_name":'분당구', "receiving_dept":'건설과 보도관리팀', "dept_team":'보도관리팀', "dept_phone":'031-729-7350', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1iCcdmLBfH7HwJ_IHeDBLR1Ei55jWQQ8o/view"},
    {"gu_name":'분당구', "receiving_dept":'건설과 건설행정팀', "dept_team":'건설행정팀', "dept_phone":'031-729-7330', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1iCcdmLBfH7HwJ_IHeDBLR1Ei55jWQQ8o/view"},
    {"gu_name":'분당구', "receiving_dept":'건설과 도로조명팀', "dept_team":'도로조명팀', "dept_phone":'031-729-8070', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1iCcdmLBfH7HwJ_IHeDBLR1Ei55jWQQ8o/view"},
    {"gu_name":'분당구', "receiving_dept":'경제교통과 교통행정팀', "dept_team":'교통행정팀', "dept_phone":'031-729-7430', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1540qe6LgmoEG8VAWZB2Qtny_pC0vvOIY/view"},
    {"gu_name":'분당구', "receiving_dept":'경제교통과 주차관리팀', "dept_team":'주차관리팀', "dept_phone":'031-729-7440', "contact_type":"PUBLISHED_TEAM_LEAD", "source_ref":"https://drive.google.com/file/d/1540qe6LgmoEG8VAWZB2Qtny_pC0vvOIY/view"},
)

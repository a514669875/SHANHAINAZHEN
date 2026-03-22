from datetime import datetime, timedelta

from app.models.procurement import Procurement
from app.models.project import Project
from app.services.archive_service import find_dual_sibling


def _make_project(db_session):
    p = Project(
        project_id="TEST-DUAL",
        project_name="双标段匹配测试",
    )
    db_session.add(p)
    db_session.flush()
    return p


def test_find_dual_sibling_uses_contract_number_pair_first(db_session):
    project = _make_project(db_session)
    base = datetime.utcnow()
    p1 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="一标段",
        contract_number="TEST-DUAL-材1",
        create_time=base,
    )
    p2 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="二标段",
        contract_number="TEST-DUAL-材2",
        create_time=base + timedelta(seconds=1),
    )
    p3 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="一标段",
        contract_number="TEST-DUAL-材3",
        create_time=base + timedelta(seconds=2),
    )
    p4 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="二标段",
        contract_number="TEST-DUAL-材4",
        create_time=base + timedelta(seconds=3),
    )
    db_session.add_all([p1, p2, p3, p4])
    db_session.commit()

    assert find_dual_sibling(db_session, p1).id == p2.id
    assert find_dual_sibling(db_session, p2).id == p1.id
    assert find_dual_sibling(db_session, p3).id == p4.id
    assert find_dual_sibling(db_session, p4).id == p3.id


def test_find_dual_sibling_falls_back_to_closest_opposite_section(db_session):
    project = _make_project(db_session)
    base = datetime.utcnow()
    p1 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="一标段",
        contract_number=None,
        create_time=base,
    )
    p2 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="二标段",
        contract_number=None,
        create_time=base + timedelta(seconds=5),
    )
    p3 = Procurement(
        project_id=project.id,
        procurement_type="材料采购",
        procurement_method="五选二",
        contract_section="二标段",
        contract_number=None,
        create_time=base + timedelta(days=10),
    )
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    assert find_dual_sibling(db_session, p1).id == p2.id

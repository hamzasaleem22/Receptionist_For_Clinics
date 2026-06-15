import pytest

from memory_tools import PatientToolset


class TestPatientToolset:
    @pytest.fixture
    def toolset(self, mock_db):
        return PatientToolset(db=mock_db, patient_id=None)

    @pytest.fixture
    def toolset_with_patient(self, mock_db):
        return PatientToolset(db=mock_db, patient_id="pat_001")

    @pytest.mark.asyncio
    async def test_create_patient_record(self, toolset, mock_db):
        mock_db.create_patient.return_value = "pat_new_001"
        result = await toolset.create_patient_record(
            first_name="Sara", last_name="Khan", phone="923001112233"
        )
        assert "Sara Khan" in result
        assert toolset._patient_id == "pat_new_001"
        mock_db.create_patient.assert_called_once_with("Sara", "Khan", phone="923001112233")

    @pytest.mark.asyncio
    async def test_remember_fact_requires_patient(self, toolset):
        result = await toolset.remember_fact(key="allergy", value="penicillin")
        assert "Create a patient record first" in result

    @pytest.mark.asyncio
    async def test_remember_fact_succeeds(self, toolset_with_patient, mock_db):
        result = await toolset_with_patient.remember_fact(key="allergy", value="penicillin")
        assert "remembered that allergy is penicillin" in result
        mock_db.remember_fact.assert_called_once_with("pat_001", "allergy", "penicillin")

    @pytest.mark.asyncio
    async def test_recall_fact_requires_patient(self, toolset):
        result = await toolset.recall_fact(key="allergy")
        assert "No patient record found" in result

    @pytest.mark.asyncio
    async def test_recall_fact_found(self, toolset_with_patient, mock_db):
        mock_db.recall_fact.return_value = "penicillin"
        result = await toolset_with_patient.recall_fact(key="allergy")
        assert "allergy: penicillin" in result

    @pytest.mark.asyncio
    async def test_recall_fact_not_found(self, toolset_with_patient, mock_db):
        mock_db.recall_fact.return_value = None
        result = await toolset_with_patient.recall_fact(key="nonexistent")
        assert "don't have any fact" in result

    @pytest.mark.asyncio
    async def test_list_facts_with_patient(self, toolset_with_patient, mock_db, sample_memories):
        mock_db.list_memories.return_value = sample_memories
        result = await toolset_with_patient.list_facts()
        assert "allergy: penicillin" in result
        assert "preferred_time: morning" in result

    @pytest.mark.asyncio
    async def test_list_facts_empty(self, toolset_with_patient, mock_db):
        mock_db.list_memories.return_value = []
        result = await toolset_with_patient.list_facts()
        assert "No facts stored" in result

    @pytest.mark.asyncio
    async def test_list_facts_requires_patient(self, toolset):
        result = await toolset.list_facts()
        assert "No patient record found" in result

    @pytest.mark.asyncio
    async def test_forget_fact_requires_patient(self, toolset):
        result = await toolset.forget_fact(key="allergy")
        assert "No patient record found" in result

    @pytest.mark.asyncio
    async def test_forget_fact_removed(self, toolset_with_patient, mock_db):
        mock_db.forget_fact.return_value = True
        result = await toolset_with_patient.forget_fact(key="allergy")
        assert "forgotten" in result

    @pytest.mark.asyncio
    async def test_forget_fact_not_found(self, toolset_with_patient, mock_db):
        mock_db.forget_fact.return_value = False
        result = await toolset_with_patient.forget_fact(key="nonexistent")
        assert "couldn't find" in result

    def test_set_patient_id(self, toolset):
        assert toolset._patient_id is None
        toolset.set_patient_id("pat_updated")
        assert toolset._patient_id == "pat_updated"

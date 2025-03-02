import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Annotated, List

from fastapi import Depends, HTTPException
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    delete,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import selectinload
from starlette_context import context

from dependencies import get_client_header
from pems_api.core.models.agency.agency import (
    CaseChargeAssociation,
    CaseRecord,
    Charge,
    DefendantContactDetails,
    DefendantDetails,
)
from pems_api.utils.aws.async_aws_client import get_s3
from pems_api.utils.aws.s3_script import S3
from pems_api.utils.database.connections import get_async_engine
from pems_api.utils.database.session_context_manager import session_context


class CaseRecordsController:

    def __init__(
        self,
        async_engine: Annotated[AsyncEngine, Depends(get_async_engine)],
        agency: str = Depends(get_client_header),
        s3_client=Depends(get_s3),
    ) -> None:
        self.async_engine = async_engine
        self.agency = agency
        self.s3_client = s3_client

    def build_filter_query(self, query) -> list:
        filters = []
        for field, value in query.dict(exclude_unset=True).items():
            column = (
                getattr(CaseRecord, field, None)
                or getattr(DefendantDetails, field, None)
                or getattr(Charge, field, None)
            )
            if column and value:
                filters.append(
                    column.ilike(f"%{value}%")
                    if field
                    in [
                        "first_name",
                        "last_name",
                        "violation_location",
                        "charge_description",
                    ]
                    else column == value
                )

        if query.search_string:
            search_filters = []
            search_date = self.parse_search_string(
                query.search_string, datetime.strptime, "%Y-%m-%d"
            )
            search_number = self.parse_search_string(query.search_string, float)

            for model in [CaseRecord, DefendantDetails, Charge]:
                for column in model.__table__.columns:
                    if isinstance(column.type, (String, Text)):
                        search_filters.append(column.ilike(f"%{query.search_string}%"))
                    elif isinstance(column.type, (Date, DateTime)) and search_date:
                        search_filters.append(column == search_date)
                    elif (
                        isinstance(column.type, (Integer, Float, Numeric))
                        and search_number is not None
                    ):
                        search_filters.append(column == search_number)

            filters.append(or_(*search_filters))

        filters.append(
            CaseRecord.violation_date.between(
                query.violation_start_date, query.violation_end_date
            )
        )
        return filters

    def parse_search_string(self, search_string, parse_func, *args):
        try:
            return parse_func(search_string, *args)
        except ValueError:
            return None

    async def search_case_records(self, query) -> List[dict]:
        filters = self.build_filter_query(query)
        async with session_context(self.async_engine, self.agency) as session:
            total_records = await self.fetch_total_records(session, filters)
            total_pages = (
                total_records + query.num_of_records - 1
            ) // query.num_of_records
            offset = (query.page - 1) * query.num_of_records

            case_records = await self.fetch_case_records(
                session, filters, offset, query.num_of_records
            )

            result_data = self.format_case_records(case_records)
            return {
                "total_pages": total_pages,
                "total_records": total_records,
                "result": result_data,
            }

    async def fetch_total_records(self, session, filters):
        count_query = (
            select(func.count(func.distinct(CaseRecord.id)))
            .select_from(CaseRecord)
            .join(DefendantDetails)
            .join(CaseChargeAssociation)
            .join(Charge)
            .filter(*filters)
        )
        return await session.scalar(count_query)

    async def fetch_case_records(self, session, filters, offset, limit):
        query = (
            select(CaseRecord)
            .distinct()
            .join(DefendantDetails)
            .join(CaseChargeAssociation)
            .join(Charge)
            .options(
                selectinload(CaseRecord.defendant),
                selectinload(CaseRecord.case_charge_associations).selectinload(
                    CaseChargeAssociation.charge
                ),
            )
            .filter(*filters)
            .offset(offset)
            .limit(limit)
            .order_by(CaseRecord.violation_date.desc(), CaseRecord.created_on.desc())
        )

        result = await session.execute(query)
        return result.scalars().all()

    def format_case_records(self, case_records):
        return [
            {
                "id": case.id,
                "hearing_date": case.hearing_date,
                "hearing_time": case.hearing_time,
                "violation_date": case.violation_date,
                "case_number": case.case_number,
                "ticket_number": case.ticket_number,
                "last_name": case.defendant.last_name if case.defendant else None,
                "middle_name": case.defendant.middle_name if case.defendant else None,
                "first_name": case.defendant.first_name if case.defendant else None,
                "charges": [
                    {
                        "charge_id": assoc.charge.id,
                        "charge_code": assoc.charge.charge_code,
                        "charge_description": assoc.charge.charge_description,
                        "charge_type": assoc.charge.charge_type,
                    }
                    for assoc in case.case_charge_associations
                    if assoc.charge
                ],
                "case_type": case.ticket_type,
            }
            for case in case_records
        ]

    async def create_case_records(self, case_data):
        async with session_context(self.async_engine, self.agency) as session:

            defendant_data = case_data.defendant
            defendant = DefendantDetails(
                **defendant_data.dict(exclude={"contacts"}),
            )
            existing_defendant = await session.execute(
                select(DefendantDetails).filter_by(ssn_id=case_data.defendant.ssn_id)
            )
            existing_defendant = existing_defendant.scalars().first()

            contact_ids = []
            if existing_defendant:
                defendant = existing_defendant

                for contact_data in case_data.defendant.contacts:
                    existing_contact = await session.execute(
                        select(DefendantContactDetails).filter_by(
                            defendant_id=defendant.id,
                            address_delivery_point=contact_data.address_delivery_point,
                            mailing_address=contact_data.mailing_address,
                            location_city_name=contact_data.location_city_name,
                            location_state_code=contact_data.location_state_code,
                            location_postal_code=contact_data.location_postal_code,
                            phone_number=contact_data.phone_number,
                        )
                    )
                    existing_contact = existing_contact.scalars().first()

                    if existing_contact:
                        contact_ids.append(existing_contact.id)
                    else:
                        contact = DefendantContactDetails(
                            **contact_data.dict(),
                            defendant_id=defendant.id,
                        )
                        session.add(contact)
                        await session.flush()
                        contact_ids.append(contact.id)
            else:
                defendant_data = case_data.defendant
                defendant = DefendantDetails(
                    **defendant_data.dict(exclude={"contacts"}),
                )
                session.add(defendant)
                await session.flush()

                for contact_data in case_data.defendant.contacts:
                    contact = DefendantContactDetails(
                        **contact_data.dict(),
                        defendant_id=defendant.id,
                    )
                    session.add(contact)
                    await session.flush()
                    contact_ids.append(contact.id)

            def make_utc_aware(dt):
                if dt and dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt

            case_record = CaseRecord(
                **case_data.dict(
                    exclude={
                        "defendant",
                        "charge_ids",
                        "issue_datetime",
                        "all_charge_start",
                        "all_charge_end",
                    }
                ),
                defendant_id=defendant.id,
                issue_datetime=make_utc_aware(case_data.issue_datetime),
                all_charge_start=make_utc_aware(case_data.all_charge_start),
                all_charge_end=make_utc_aware(case_data.all_charge_end),
            )
            session.add(case_record)
            await session.flush()

            for charge_id in case_data.charge_ids:
                charge = await session.get(Charge, charge_id)
                if not charge:
                    raise HTTPException(
                        status_code=404, detail=f"Charge ID {charge_id} not found."
                    )
                association = CaseChargeAssociation(
                    case_record_id=case_record.id,
                    charge_id=charge_id,
                )
                session.add(association)

            await session.commit()

            return {"message": "insertion successful"}

    async def fetch_case_record(self, case_number):
        async with session_context(self.async_engine, self.agency) as session:
            query = (
                select(CaseRecord)
                .distinct()
                .join(DefendantDetails)
                .join(DefendantContactDetails)
                .join(CaseChargeAssociation)
                .join(Charge)
                .options(
                    selectinload(CaseRecord.defendant).selectinload(
                        DefendantDetails.contacts
                    ),
                    selectinload(CaseRecord.case_charge_associations).selectinload(
                        CaseChargeAssociation.charge
                    ),
                )
                .filter(CaseRecord.case_number == case_number)
            )

            result = await session.execute(query)
            result = result.scalars().one_or_none()

            if result:
                result = result.to_dict()
                charge_ids = []
                case_charge_associations = result.pop("case_charge_associations", [])

                for case_charge in case_charge_associations:
                    charge_ids.append(case_charge["charge"]["id"])

                result["charge_ids"] = charge_ids

                return result

            else:
                raise HTTPException(status_code=404, detail="Case not found")

    async def get_all_defendants(self):
        async with session_context(self.async_engine, self.agency) as session:
            query = (
                select(DefendantDetails)
                .join(DefendantContactDetails)
                .options(selectinload(DefendantDetails.contacts))
            )

            result = await session.execute(query)

            if result:
                result = result.scalars().all()
                return result

            else:
                raise HTTPException(status_code=404, detail="No Defendants Available")

    async def get_all_charges(self):
        async with session_context(self.async_engine, self.agency) as session:
            result = await session.scalars(select(Charge))
            result = result.all()
            if result:
                return result

            else:
                raise HTTPException(status_code=404, detail="No Charges Available")

    async def update_case_record(self, case_number, case_data):
        async with session_context(self.async_engine, self.agency) as session:
            existing_case = await session.execute(
                select(CaseRecord).filter(CaseRecord.case_number == case_number)
            )
            existing_case = existing_case.scalars().first()

            if not existing_case:
                raise HTTPException(
                    status_code=404, detail=f"Case ID {case_number} not found."
                )

            defendant_data = case_data.defendant
            existing_defendant = await session.execute(
                select(DefendantDetails).filter_by(ssn_id=defendant_data.ssn_id)
            )
            existing_defendant = existing_defendant.scalars().first()

            if existing_defendant:

                for key, value in defendant_data.dict(exclude={"contacts"}).items():
                    setattr(existing_defendant, key, value)
            else:

                new_defendant = DefendantDetails(
                    **defendant_data.dict(exclude={"contacts"}),
                )
                session.add(new_defendant)
                await session.flush()
                existing_defendant = new_defendant

            contact_ids = []
            for contact_data in defendant_data.contacts:
                existing_contact = await session.execute(
                    select(DefendantContactDetails).filter_by(
                        defendant_id=existing_defendant.id,
                        address_delivery_point=contact_data.address_delivery_point,
                        mailing_address=contact_data.mailing_address,
                        location_city_name=contact_data.location_city_name,
                        location_state_code=contact_data.location_state_code,
                        location_postal_code=contact_data.location_postal_code,
                        phone_number=contact_data.phone_number,
                    )
                )
                existing_contact = existing_contact.scalars().first()

                if existing_contact:

                    for key, value in contact_data.dict().items():
                        setattr(existing_contact, key, value)
                    contact_ids.append(existing_contact.id)
                else:

                    new_contact = DefendantContactDetails(
                        **contact_data.dict(),
                        defendant_id=existing_defendant.id,
                    )
                    session.add(new_contact)
                    await session.flush()
                    contact_ids.append(new_contact.id)

            def make_utc_aware(dt):
                if dt and dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt

            for key, value in case_data.dict(
                exclude={
                    "defendant",
                    "charge_ids",
                    "issue_datetime",
                    "all_charge_start",
                    "all_charge_end",
                }
            ).items():
                setattr(existing_case, key, value)

            existing_case.defendant_id = existing_defendant.id
            existing_case.issue_datetime = make_utc_aware(case_data.issue_datetime)
            existing_case.all_charge_start = make_utc_aware(case_data.all_charge_start)
            existing_case.all_charge_end = make_utc_aware(case_data.all_charge_end)

            await session.execute(
                delete(CaseChargeAssociation).filter_by(case_record_id=existing_case.id)
            )
            for charge_id in case_data.charge_ids:
                charge = await session.get(Charge, charge_id)
                if not charge:
                    raise HTTPException(
                        status_code=404, detail=f"Charge ID {charge_id} not found."
                    )
                association = CaseChargeAssociation(
                    case_record_id=existing_case.id,
                    charge_id=charge_id,
                )
                session.add(association)

            await session.commit()

            return {"message": "Update successful"}

    def _get_file_details(self, file):
        filename, file_extension = os.path.splitext(file.filename)
        data_name = file_extension.lower()

        if data_name[1:] != "xml":
            raise HTTPException(
                400, "File type should be one of type xml when uploading."
            )

        details = {
            "filename": filename,
            "data_type": "DOCUMENT",
            "data_name": data_name,
        }
        return details

    def resolve_path(self, root, path):
        namespaces = {
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "j": "http://niem.gov/niem/domains/jxdm/4.0",
            "nc": "http://niem.gov/niem/niem-core/2.0",
            "s": "http://niem.gov/niem/structures/2.0",
            "jsi": "http://www.justicesystems.com/iepd",
        }
        element = root.find(path, namespaces=namespaces)
        if element is None:
            return ""
        return element.text.strip() if element.text else ""

    async def _get_case_number_from_xml(self, xml_file):
        content = await xml_file.read()
        root = ET.fromstring(content)

        case_number = self.resolve_path(root, ".//j:Citation//nc:IdentificationID")

        return case_number

    async def _upload_file_data_to_s3(self, file_data, created_on):
        uploaded_file = file_data.get("data")
        data_type = file_data.get("data_type")

        file_size = os.fstat(uploaded_file.file.fileno()).st_size
        if data_type == "DOCUMENT":
            if file_size > 5000000:
                raise HTTPException(400, "File too large")

        case_number = await self._get_case_number_from_xml(uploaded_file)
        await uploaded_file.seek(0)
        filename = "{}{}".format(case_number, file_data.get("data_name"))
        key_parts = ["Case", "XML", created_on, filename]
        meta = {
            "created_by": context.get("user_details")["user_name"],
            "filename": filename,
            "data_type": data_type,
            "created_on": created_on,
            "case_number": case_number,
        }

        uploaded = await S3(s3_client=self.s3_client).upload(
            "/".join(key_parts), uploaded_file, metadata=meta
        )
        return uploaded

    async def upload_xml(self, upload_files, created_on):
        success = 1
        failed_files = []
        uploaded_files = upload_files
        if upload_files in (None, ""):
            success = 0
            return {"success": success, "failed_files": failed_files}

        file_details = []
        for file in uploaded_files:
            file_detail = self._get_file_details(file)
            file_details.append((file, file_detail))

        for file_detail in file_details:
            single_file_details = dict(data=file_detail[0], **file_detail[1])
            try:
                single_file_success = await self._upload_file_data_to_s3(
                    single_file_details, created_on
                )
                if not single_file_success:
                    failed_files.append(file_detail[1].get("filename"))
                    success = 0
            except Exception as e:
                failed_files.append(file_detail[1].get("filename"))
                success = 0

        return {"success": success, "failed_files": failed_files}

    async def get_all_xml(self, created_on=None):
        case_document_links = []
        all_documents = await S3(s3_client=self.s3_client).list_files(
            "Case/XML" + (f"/{created_on}" if created_on else "")
        )

        for document in all_documents:
            splitter = document.get("Key", "").split("/")[-1]
            if splitter == "":
                continue

            obj = (
                await S3(s3_client=self.s3_client).get_metadata(document.get("Key", ""))
                or {}
            )

            signed_url = await S3(s3_client=self.s3_client).get_signed_url(
                key=document.get("Key", ""), expiration=300
            )

            if not obj.get("filename"):
                obj["filename"] = splitter

            document_entry = {
                "data": signed_url,
                "meta": obj,
                "key": document.get("Key", ""),
            }

            document_entry["data_type"] = "document"

            case_document_links.append(document_entry)
            # except Exception as e:
            #     raise HTTPException(400, str(e))
        return case_document_links

    async def parse_citation_xml(self, key):
        file = await S3(s3_client=self.s3_client).get_file_obj(key=key)
        root = ET.fromstring(file)

        mapper = {
            "citation": {
                "issuing_official_name": "",
                "all_charge_end": "",
                "room_number": "",
                "driving_incident_legal_speed_rate": self.resolve_path(
                    root,
                    ".//jsi:DrivingIncident//j:DrivingIncidentLegalSpeedRate/nc:MeasureText",
                ),
                "additional_notes": self.resolve_path(
                    root,
                    ".//j:Citation//j:CitationViolation//nc:IncidentObservationText",
                ),
                "violation_date": self.resolve_path(root, "j:Citation//nc:Date"),
                "driving_incident_recorded_speed_rate": self.resolve_path(
                    root,
                    ".//jsi:DrivingIncident//j:DrivingIncidentRecordedSpeedRate/nc:MeasureText",
                ),
                "violation_order": "",
                "is_active": True,
                "created_on": "",
                "ticket_type": "Traffic",
                "violation_location": self.resolve_path(
                    root,
                    ".//j:Citation//j:CitationIssuedLocation//nc:LocationDescriptionText",
                ),
                "vehicle_year": "",
                "warrant_number": "",
                "modified_by": "",
                "ticket_number": self.resolve_path(
                    root,
                    ".//j:Citation//j:CitationViolation//nc:ActivityIdentification//nc:IdentificationID",
                ),
                "county_name": "",
                "issue_datetime": self.resolve_path(root, ".//j:Citation//nc:Date"),
                "vehicle_make": "",
                "bench_warrant_number": None,
                "modified_on": "",
                "case_number": self.resolve_path(
                    root, ".//j:Citation//nc:IdentificationID"
                ),
                "observation_text": "",
                "vehicle_model": "",
                "pd_reference_number": None,
                "hearing_date": self.resolve_path(
                    root, ".//j:CourtAppearanceDate//nc:DateTime"
                ),
                "location_description_text": self.resolve_path(
                    root,
                    ".//j:Citation//j:CitationIssuedLocation//nc:LocationDescriptionText",
                ),
                "vehicle_registration_plate_no": self.resolve_path(
                    root,
                    ".//nc:ConveyanceRegistrationPlateIdentification//nc:IdentificationID",
                ),
                "defendant_id": None,
                "hearing_time": self.resolve_path(
                    root, ".//j:CourtAppearanceDate//nc:DateTime"
                ),
                "issuing_official_badge_number": self.resolve_path(
                    root,
                    ".//j:EnforcementOfficialBadgeIdentification/nc:IdentificationID",
                ),
                "all_charge_start": "",
            },
            "defendant": {
                "first_name": self.resolve_path(
                    root, ".//nc:Person//nc:PersonName/nc:PersonGivenName"
                ),
                "sex": self.resolve_path(root, ".//nc:Person//nc:PersonSexCode"),
                "is_active": True,
                "ethnicity": self.resolve_path(
                    root, ".//nc:Person//nc:PersonEthnicityText"
                ),
                "created_by": "",
                "eye_color": self.resolve_path(
                    root, ".//nc:Person//nc:PersonEyeColorCode"
                ),
                "created_on": "",
                "middle_name": self.resolve_path(
                    root, ".//nc:Person//nc:PersonName/nc:PersonMiddleName"
                ),
                "hair_color": self.resolve_path(
                    root, ".//nc:Person//nc:PersonHairColorCode"
                ),
                "modified_by": "",
                "last_name": self.resolve_path(
                    root, ".//nc:Person//nc:PersonName/nc:PersonSurName"
                ),
                "height": self.resolve_path(
                    root, ".//nc:Person//nc:PersonHeightDescriptionText"
                ),
                "modified_on": "",
                "ssn_id": self.resolve_path(
                    root, ".//nc:Person//nc:PersonSSNIdentification/nc:IdentificationID"
                ),
                "suffix": self.resolve_path(
                    root, ".//nc:Person//nc:PersonName/nc:PersonNameSuffixText"
                ),
                "weight": self.resolve_path(
                    root, ".//nc:Person//nc:PersonWeightDescriptionText"
                ),
                "dob": self.resolve_path(
                    root, ".//nc:Person//nc:PersonBirthDate/nc:Date"
                ),
                "license_number": self.resolve_path(
                    root,
                    ".//nc:Person//nc:PersonLicenseIdentification/nc:IdentificationID",
                ),
                "race": self.resolve_path(root, ".//nc:Person//nc:PersonRaceCode"),
                "license_state_code": self.resolve_path(
                    root,
                    ".//nc:Person//nc:PersonLicenseIdentification/j:IdentificationJurisdictionNCICLSTACode",
                ),
                "contacts": [
                    {
                        "mailing_address": self.resolve_path(
                            root, ".//nc:StructuredAddress//nc:AddressDeliveryPointText"
                        ),
                        "location_city_name": self.resolve_path(
                            root, ".//nc:StructuredAddress//nc:LocationCityName"
                        ),
                        "location_postal_code": self.resolve_path(
                            root,
                            ".//nc:StructuredAddress//nc:LocationStateUSPostalServiceCode",
                        ),
                        "created_by": "",
                        "modified_by": "",
                        "address_delivery_point": self.resolve_path(
                            root, ".//nc:StructuredAddress//nc:AddressDeliveryPointText"
                        ),
                        "location_state_code": self.resolve_path(
                            root,
                            ".//nc:StructuredAddress//nc:LocationStateUSPostalServiceCode",
                        ),
                        "phone_number": self.resolve_path(
                            root, ".//nc:TelephoneNumberFullID"
                        ),
                        "is_active": True,
                        "created_on": "",
                        "modified_on": "",
                    }
                ],
            },
            "charges": [
                {
                    "charge_code": self.resolve_path(
                        charge,
                        ".//j:StatuteCodeIdentification/nc:IdentificationID",
                    ),
                    "charge_description": self.resolve_path(
                        charge,
                        ".//j:StatuteDescriptionText",
                    ),
                }
                for charge in root.findall(
                    ".//j:ChargeStatute",
                    namespaces={
                        "j": "http://niem.gov/niem/domains/jxdm/4.0",
                    },
                )
            ],
        }

        return mapper
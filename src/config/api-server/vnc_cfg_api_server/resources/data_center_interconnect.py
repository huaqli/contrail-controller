#
# Copyright (c) 2018 Juniper Networks, Inc. All rights reserved.
#

from vnc_api.gen.resource_common import DataCenterInterconnect

from vnc_cfg_api_server.resources._resource_base import ResourceMixin


class DataCenterInterconnectServer(ResourceMixin, DataCenterInterconnect):

    @classmethod
    def pre_dbe_create(cls, tenant_name, obj_dict, db_conn):
        # make sure referenced LRs belongs to different fabrics
        return cls._make_sure_lrs_belongs_to_different_fabrics(
            db_conn, obj_dict)

    @classmethod
    def _make_sure_lrs_belongs_to_different_fabrics(cls, db_conn, dci):
        lr_list = []
        for lr_ref in dci.get('logical_router_refs') or []:
            lr_uuid = lr_ref.get('uuid')
            if lr_uuid:
                lr_list.append(lr_uuid)

        if not lr_list:
            return True, ''

        for lr_uuid in lr_list:
            ok, read_result = cls.dbe_read(
                db_conn, 'logical_router', lr_uuid, obj_fields=[
                    'physical_router_refs',
                    'data_center_interconnect_back_refs'])

            if not ok:
                return False, read_result

            lr = read_result
            # check there are no more than one DCI back ref for this LR
            # it is acceptable that dci object can associate with a lr,
            # but lr not associated with any PRs yet
            # make sure LR update should check for this association
            if len(lr.get('data_center_interconnect_back_refs') or []) > 1:
                msg = ("Logical router can not associate with  more than one "
                       "DCI: %s" % lr_uuid)
                return False, (400, msg)
            if len(lr.get('data_center_interconnect_back_refs') or []) == 1:
                dci_ref = lr.get('data_center_interconnect_back_refs')[0]
                if dci.get('fq_name') != dci_ref.get('to'):
                    msg = ("Logical router can not associate with more than "
                           "one DCI: %s" % lr_uuid)
                    return False, (400, msg)
            init_fab = None
            for pr_ref in read_result.get('physical_router_refs') or []:
                pr_uuid = pr_ref.get('uuid')
                status, pr_result = cls.dbe_read(
                    db_conn, 'physical_router', pr_uuid, obj_fields=[
                        'fabric_refs'])
                if not status:
                    return False, pr_result

                if pr_result.get("fabric_refs"):
                    # pr can be associated to only one Fabric, if not, many
                    # other system components will fail fabric implementation
                    # must ensure this, no need to double check
                    fab_id = pr_result["fabric_refs"][0].get('uuid')
                    if init_fab and init_fab != fab_id:
                        msg = ("Logical router can not associate with PRs "
                               "belonging to different DCI connected Fabrics: "
                               "%s" % lr_uuid)
                        return False, (400, msg)
                    else:
                        init_fab = fab_id
            if not init_fab:
                msg = ("DCI Logical router is not associated to any fabric: %s"
                       % lr_uuid)
                return False, (400, msg)
        return True, ''

    @classmethod
    def pre_dbe_update(cls, id, fq_name, obj_dict, db_conn, **kwargs):
        ok, read_result = cls.dbe_read(db_conn, 'data_center_interconnect',
                                       id, obj_fields=['logical_router_refs'])
        if not ok:
            return ok, read_result

        # make sure referenced LRs belongs to different fabrics
        return cls._make_sure_lrs_belongs_to_different_fabrics(
            db_conn, read_result)

"""一键加载 MetaphorSHG 资源包。"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

def load_resources():
    from metaphor_graph.ontology import CascadeOntology, CascadeSpec, FrameSpec, TYPE_CONSTRAINTS
    with open(os.path.join(HERE, "ontology_default.json"), encoding="utf-8") as f:
        payload = json.load(f)
    ont = CascadeOntology()
    for fd in payload["frames"]:
        spec = FrameSpec(**fd)
        TYPE_CONSTRAINTS.setdefault(spec.source_type, [])
        if spec.mapping_type not in TYPE_CONSTRAINTS[spec.source_type]:
            TYPE_CONSTRAINTS[spec.source_type].append(spec.mapping_type)
        ont.frames.setdefault(spec.id, spec)
    for cd in payload["cascades"]:
        ont.cascades.setdefault(cd["id"], CascadeSpec(**cd))
    ont._trigger_index = {}
    for fid, fr in ont.frames.items():
        for t in fr.triggers:
            ont._trigger_index.setdefault(t, []).append(fid)
    ont._frame_to_cascade = {}
    for cid, c in ont.cascades.items():
        for fid in c.member_frames:
            ont._frame_to_cascade[fid] = cid
    bilingual = json.load(open(os.path.join(HERE, "ontology_bilingual.json"),
                               encoding="utf-8"))
    return ont, bilingual

if __name__ == "__main__":
    ont, bilingual = load_resources()
    print(f"本体: {len(ont.frames)} 框架 / {len(ont.cascades)} 级联; "
          f"双语对齐 {sum(1 for a in bilingual['alignments'].values() if a['en_name'])} 条")

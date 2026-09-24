// ============================================================================
// 隐喻超超图 / 元图 —— Neo4j 属性图 schema（方案 §4.6 存储选型）
//
// 核心思想：超图与属性图同构。一条 L1 隐喻超边 = 一个 :MetaphorMapping 节点，
// 它通过多条关系（HAS_SOURCE / HAS_TARGET / HAS_GROUND）连接多个端点，
// 从而表达「n 元 / 喻底集合」的超边语义。L2/L3 的「元」语义用
// :MetaphorFrame / :MetaphorCascade 节点 + IN_FRAME / IN_CASCADE 关系承载。
// ============================================================================

// ---------------------- 节点标签 ----------------------
// :Domain        源域 / 目标域 / 喻底概念（端点）
// :MetaphorMapping   L1 隐喻超边（layer=1 或 1.5 扩展）
// :MetaphorFrame     L2 一般隐喻（超顶点，layer=2）
// :MetaphorCascade   L3 隐喻级联（超超顶点，layer=3）
// :Chunk         原始文本块（用于溯源与召回）

// ---------------------- 关系类型 ----------------------
// (Mapping)-[:HAS_SOURCE]->(Domain)
// (Mapping)-[:HAS_TARGET]->(Domain)
// (Mapping)-[:HAS_GROUND]->(Domain)        // 喻底集合（超边多端点）
// (Mapping)-[:IN_FRAME]->(Frame)
// (Frame)-[:IN_CASCADE]->(Cascade)
// (Mapping)-[:SPANS]->(Chunk)              // 可跨多个 chunk（L1.5）

// ---------------------- 索引（性能） ----------------------
CREATE INDEX IF NOT EXISTS FOR (m:MetaphorMapping) ON (m.id);
CREATE INDEX IF NOT EXISTS FOR (f:MetaphorFrame) ON (f.id);
CREATE INDEX IF NOT EXISTS FOR (c:MetaphorCascade) ON (c.id);
CREATE INDEX IF NOT EXISTS FOR (d:Domain) ON (d.name);
CREATE INDEX IF NOT EXISTS FOR (m:MetaphorMapping) ON (m.layer);
CREATE INDEX IF NOT EXISTS FOR (ch:Chunk) ON (ch.id);

// ---------------------- 唯一性约束（MERGE 幂等写入的前提） ----------------------
// 没有约束，MERGE 无法保证不产生重复节点，增量摄入就会退化成「每次都新建」。
CREATE CONSTRAINT mapping_id IF NOT EXISTS FOR (m:MetaphorMapping) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT frame_id IF NOT EXISTS FOR (f:MetaphorFrame) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT cascade_id IF NOT EXISTS FOR (c:MetaphorCascade) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.id IS UNIQUE;

// ---------------------- 类型安全约束（§4.1.3，防字面误判） ----------------------
// 通过约束 (:Domain)-[:OF_TYPE]->(:DomainType) 与映射类型白名单实现结构化过滤，
// 不依赖 LLM 判断。等价逻辑见 ontology.TYPE_CONSTRAINTS。
//
// 示例：PHYSICAL_OBJECT 只能参与 OBJECT_IS_CONTAINER / OBJECT_IS_INSTRUMENT
//       MOTION 只能参与 CHANGE_IS_MOTION / PROGRESS_IS_JOURNEY

// ---------------------- 查询模板 ----------------------

// 模板 1：跨域检索（§4.4.1）
//   查询触发词 → 其框架 → 所属级联 → 该级联下所有 target=项目困境 的 chunk
// MATCH (d:Domain {name:'泥潭'})<-[:HAS_SOURCE]-(m:MetaphorMapping)-[:IN_FRAME]->(f)
// MATCH (f)-[:IN_CASCADE]->(c:MetaphorCascade)
// MATCH (c)<-[:IN_CASCADE]-(f2)<-[:IN_FRAME]-(m2:MetaphorMapping)-[:HAS_TARGET]->(t:Domain {name:'项目困境'})
// MATCH (m2)-[:SPANS]->(ch:Chunk)
// RETURN ch.text, m2.confidence ORDER BY m2.confidence DESC LIMIT 10;

// 模板 2：多线索汇聚（§4.4.2）
//   返回被 ≥2 个触发词共同指向的目标域
// MATCH (t:Domain)<-[:HAS_TARGET]-(m:MetaphorMapping)-[:HAS_SOURCE]->(s:Domain)
// WHERE s.name IN ['猪','燕尾服','宴席']
// RETURN t.name, count(m) AS support ORDER BY support DESC;

// 模板 3：沿级联下钻（U-Retrieval 逐层下钻，§4.3.2）
// MATCH (c:MetaphorCascade {name:'PROGRESS_IS_JOURNEY'})
//        <-[:IN_CASCADE]-(f:MetaphorFrame)<-[:IN_FRAME]-(m:MetaphorMapping)
// RETURN f.name, m.source, m.target, m.ground;

// 模板 4：扩展隐喻跨 chunk 召回（§4.2）
// MATCH (m:MetaphorMapping {isExtended:true})-[:SPANS]->(ch:Chunk)
// RETURN m.id, collect(ch.id) AS chunks, m.ground;

// 模板 5：喻底交集（扩展隐喻合并判据第三条，依赖 HAS_GROUND）
//   喻底是超边「多端点」语义的来源。此前 ground 只作为 JSON 数组属性存在，
//   无法图遍历，本判据只能退化成数组交运算。现在可按图查询：
// MATCH (a:MetaphorMapping)-[:HAS_GROUND]->(g:Domain)<-[:HAS_GROUND]-(b:MetaphorMapping)
// WHERE a.id <> b.id AND a.frame_id = b.frame_id
// RETURN a.id, b.id, count(g) AS shared_ground
// ORDER BY shared_ground DESC;

// 模板 6：证据链溯源与冲突消解（知识管理 · 演化）
// MATCH (m:MetaphorMapping)-[:SUPPORTED_BY]->(v:Evidence)
// WITH m, count(v) AS support, avg(v.authority) AS authority, max(v.timestamp) AS latest
// RETURN m.id, m.deprecated, support, authority, latest
// ORDER BY authority DESC, support DESC;

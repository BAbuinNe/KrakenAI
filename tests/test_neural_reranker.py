"""Deterministic tests; actual neural model weights are not downloaded in CI."""
from app.neural_reranker import rerank_evidence
from app.ranking import build_ranking


def test_lexical_retrieval_explains_but_does_not_override(monkeypatch):
    monkeypatch.setenv('EVIDENCE_RERANKER','lexical')
    result={'requirements':[{'parameter':'Оперативная память'}],
            'suppliers':[{'name':'A.docx','checks':[{
                'parameter':'Оперативная память',
                'requirement_source':'Оперативная память не менее 16 ГБ',
                'status':'fail','mandatory':True}]}]}
    offers=[('A.docx','Оперативная память: 8 ГБ\nКорпус: алюминий')]
    evidence=rerank_evidence(result,offers)
    assert evidence['mode']=='lexical'
    assert evidence['results'][0]['fragments'][0]['quote']=='Оперативная память: 8 ГБ'
    assert result['suppliers'][0]['checks'][0]['status']=='fail'


def test_crossencoder_stub_returns_model_scores(monkeypatch):
    from app import neural_reranker
    class FakeModel:
        def predict(self,pairs,**kwargs):
            return [0.9 if 'ОЗУ' in p[1] else -0.5 for p in pairs]
    monkeypatch.setenv('EVIDENCE_RERANKER','cross_encoder')
    monkeypatch.setattr(neural_reranker,'_model',lambda:FakeModel())
    result={'suppliers':[{'name':'A','checks':[{'parameter':'Память',
            'requirement_source':'Оперативная память 16 ГБ','status':'unknown','mandatory':True}]}]}
    r=rerank_evidence(result,[('A','SSD 512 ГБ\nОЗУ 16 ГБ')])
    assert r['mode']=='cross_encoder'
    assert r['results'][0]['fragments'][0]['quote']=='ОЗУ 16 ГБ'
    assert r['results'][0]['fragments'][0]['relevance_score']==0.9


def test_tz_rubric_ranks_only_fully_verified_optional_criteria():
    r={'engine':'requirements-v2','requirements':[
         {'section':'3.2','mandatory':True,'parameter':'Ядра'},
         {'section':'4.1','mandatory':False,'weight':75,'parameter':'Экран'},
         {'section':'4.2','mandatory':False,'weight':25,'parameter':'Корпус'}],
       'suppliers':[]}
    for name,screen,body in [('A','pass','fail'),('B','fail','pass')]:
        r['suppliers'].append({'name':name,'mandatory_failed':0,'mandatory_unknown':0,
             'checks':[{'section':'3.2','mandatory':True,'status':'pass'},
                       {'section':'4.1','mandatory':False,'status':screen},
                       {'section':'4.2','mandatory':False,'status':body}],
             'passed':2,'failed':1,'unknown':0,'facts':[]})
    ranking=build_ranking(r)
    assert ranking['active_criteria']==['tz_rubric']
    assert ranking['recommended']=='A'
    assert ranking['ranked'][0]['score']==75
    r['suppliers'][0]['checks'][1]['status']='unknown'
    incomplete=build_ranking(r)
    assert incomplete['recommended'] is None
    assert incomplete['tz_rubric']['complete'] is False


def test_failed_mandatory_is_never_ranked():
    r={'requirements':[{'mandatory':True}], 'suppliers':[{'name':'A',
       'mandatory_failed':1,'mandatory_unknown':0,
       'checks':[{'mandatory':True,'status':'fail'}], 'facts':[]}]}
    ranking=build_ranking(r)
    assert not ranking['ranked']
    assert ranking['recommended'] is None

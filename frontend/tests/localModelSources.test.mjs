import test from 'node:test';
import assert from 'node:assert/strict';
import {hasConfiguredProviders} from '../src/constants/oauthProviders.js';
import {getModelVisuals} from '../src/utils/modelHelpers.js';
test('a sole connected local provider prevents the add-cloud-credentials gate',()=>{
  assert.equal(hasConfiguredProviders({local_model_url:'http://127.0.0.1:1234/v1',enabled_providers:{local:true}}),true);
  assert.equal(hasConfiguredProviders({local_model_url:'http://127.0.0.1:1234/v1',enabled_providers:{local:false}}),false);
  assert.equal(hasConfiguredProviders({custom_endpoint_url:'https://example.invalid/v1'}),true);
});
test('local OpenAI-compatible models are visually identified as local',()=>{
  assert.equal(getModelVisuals('local:qwen').name,'本地模型');
  assert.equal(getModelVisuals('local:gpt-fixture').short,'Local');
});

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')

text = 'Ai powerd healthcare startup fo rural areas'

embedding = model.encode(text)

print('Vector length: ', len(embedding))
print('First 10 values: ', embedding[:10])


text1 = 'Ai healthcare startup'
text2 = 'Investing in medical AI companies'

emb1 = model.encode(text1)
emb2 = model.encode(text2)

similarity = cosine_similarity([emb1], [emb2])

print('Similarity Score: ', similarity[0][0])